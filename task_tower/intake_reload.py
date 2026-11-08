"""Append-only operator configuration changes; never an HTTP authorization source."""
from copy import deepcopy


def extend_config(previous, candidate, field):
    if {k:v for k,v in previous.items() if k!=field}!={k:v for k,v in candidate.items() if k!=field}:
        raise ValueError('immutable_operator_setting_changed')
    old,new=previous[field],candidate[field]
    if field=='approved_plans':
        if set(new)-set(previous['projects']):raise ValueError('project_forbidden')
        if any(not set(values)<=set(new.get(project,())) for project,values in old.items()):
            raise ValueError('approval_removal_requires_restart')
    elif field=='assignments':
        def mapping(rows):
            result={}
            for row in rows:
                key=(row['project_id'],row['bead_id'])
                if key in result:raise ValueError('duplicate_assignment')
                result[key]=row
            return result
        a,b=mapping(old),mapping(new)
        if any(b.get(key)!=value for key,value in a.items()):raise ValueError('assignment_changed')
    else:raise ValueError('unsupported_reload')
    return deepcopy(candidate)
