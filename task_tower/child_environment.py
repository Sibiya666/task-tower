"""Model/check/native children do not inherit trusted host integration secrets."""
def child_environment(environment):
    exact={"GH_TOKEN","GITHUB_TOKEN","GIT_ASKPASS","SSH_ASKPASS"}
    prefixes=("WEBHOOK_","GITHUB_APP_","TT_GITHUB_","TASK_TOWER_APP_")
    return {k:v for k,v in environment.items() if k.upper() not in exact and not k.upper().startswith(prefixes)}
