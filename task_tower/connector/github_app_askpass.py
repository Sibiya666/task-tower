"""Fixed Git credential channel. Never invoked by models or logged."""
import os
import sys
if __name__ == "__main__":
    prompt=" ".join(sys.argv[1:]).lower()
    if "username" in prompt: print("x-access-token")
    elif "password" in prompt: print(os.environ["TT_GITHUB_INSTALLATION_TOKEN"])
    else: raise SystemExit(1)
