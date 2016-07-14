# The Scorebot

The scorebot is responsible for checking the service status of all teams. It updates
flags on the vulnerable services, and checks that these flags are accessible. Each
service has at least one <i>setflag</i> and one <i>getflag</i> and optionally one
<i>benign</i> script. The <i>setflag</i> and <i>getflag</i> scripts are used to check
the status of the service by setting and getting the flags, while the <i>benign</i>
script is used to create some benign traffic. Scorebot pulls these scripts and
corresponding execution intervals from the database. In addition, the scorebot also
invokes all exploit containers using invoke_container.py and updates the scores of
all teams.
