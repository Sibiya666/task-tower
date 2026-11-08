"""Append-only operator configuration changes; never an HTTP authorization source."""
from copy import deepcopy
from pathlib import Path
from .project_connections import safe_config_path


def read_document(path):
    with safe_config_path(Path(path)).open('rb') as stream:raw=stream.read(65537)
    if len(raw)>65536:raise ValueError('configuration_limit')
    return raw


class ConfigReloader:
    """Validate changed operator bytes once; failed versions never advance authority."""
    def __init__(self,path,current,field,loader):
        self.path,self.current,self.field,self.loader=path,current,field,loader
        self.document=None

    def __call__(self):
        raw=read_document(self.path)
        if raw==self.document:return self.current
        candidate=self.loader(self.path,document=raw)
        current=extend_config(self.current,candidate,self.field)
        self.current,self.document=current,raw
        return current


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
