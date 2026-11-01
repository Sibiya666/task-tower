"""Explicit GitHub Project projection; Issues remain authoritative."""
import argparse
import json
import re

from .github_source import MAX_BYTES, GitHubSourceError
from .github_tasks import GitHubTasks, _transport, task_status
from .project_connections import load_connections

ADD = '''mutation($project:ID!,$content:ID!){addProjectV2ItemById(input:{projectId:$project,contentId:$content}){item{id}}}'''
STATUS = '''mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:{singleSelectOptionId:$option}}){projectV2Item{id}}}'''


def _node(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', value):
        raise ValueError('Invalid Project or Issue node ID')
    return value


def sync_issue(connection, store, number, *, graphql=None, verified_status=None):
    if type(number) is not int or number < 1:
        raise ValueError('Invalid Issue number')
    identity = connection.repository + '#' + str(number)
    board = connection.board
    if board is None:
        return dict(identity=identity, status='not_configured')
    project, field = _node(board['project_id']), _node(board['status_field_id'])
    issue = store.get(number)
    if issue.get('number') != number or 'pull_request' in issue:
        raise ValueError('Invalid Issue identity')
    content = _node(issue.get('node_id'))
    from .project_worker import issue_lifecycle
    metadata = issue_lifecycle(store, issue)
    status = verified_status(issue) if verified_status else task_status(metadata)
    option = board['status_options'].get(status)
    if option is None:
        raise ValueError('Project has no mapping for Issue status')
    option = _node(option)

    def request(query, variables):
        try:
            raw = (store.transport or _transport)(
                'POST', 'https://api.github.com/graphql', dict(store.headers),
                {'query': query, 'variables': variables}, MAX_BYTES)
            if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
                raise ValueError()
            payload = json.loads(raw)
            if payload.get('errors') or not isinstance(payload.get('data'), dict):
                raise ValueError()
            return payload['data']
        except Exception:
            raise GitHubSourceError('Project API unavailable or insufficient permissions') from None

    try:
        execute = graphql or request
        added = execute(ADD, {'project': project, 'content': content})
        item = _node(added['addProjectV2ItemById']['item']['id'])
        updated = execute(STATUS, {'project': project, 'item': item, 'field': field, 'option': option})
        if updated['updateProjectV2ItemFieldValue']['projectV2Item']['id'] != item:
            raise ValueError()
        return dict(identity=identity, status='synced', issue_status=status, item_id=item)
    except Exception:
        # Adding an existing item is idempotent. If status publication failed,
        # the next explicit sync can safely retry both mutations.
        return dict(identity=identity, status='unavailable',
                    detail='Project projection failed; check connection, mapping and Project permissions')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--issue', required=True, type=int)
    args = parser.parse_args(argv)
    try:
        connections = load_connections(args.config)
        connection = next((row for row in connections if row.id == args.project), None)
        if connection is None:
            raise ValueError('Unknown project')
        from .github_source import GitHubSource, resolve_token
        from .project_worker import issue_lifecycle, verified_done
        token = resolve_token()
        store = GitHubTasks(connection, token=token)
        source = GitHubSource(connection.repository, token=token)
        def status(issue):
            metadata = issue_lifecycle(store, issue)
            if metadata and metadata.get('status') == 'done' and verified_done(connection, store, source, issue):
                return 'done'
            return task_status(metadata)
        result = sync_issue(connection, store, args.issue, verified_status=status)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] == 'synced' else 1
    except (ValueError, GitHubSourceError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
