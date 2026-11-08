import os, tempfile
from pathlib import Path
from trabasist_server.tools.device_setup import add_credentials
from trabasist_server.tools.inventory import get_credentials

tricky = "p#ss w'rd\\\"$x ${HOME} end\\"
env = Path(tempfile.mkdtemp()) / ".env"
add_credentials(env, "TRICKY", "someuser", tricky)

os.environ["TRABASIST_ENV"] = str(env)
c = get_credentials("TRICKY")
del os.environ["TRABASIST_ENV"]

print("username ok:", c.username == "someuser")
print("tricky password read back exactly:", c.password == tricky)
print("password hidden in repr:", tricky not in repr(c))
