# Container creator

The container creator creates all the service container images. It replaces the
vmcreator component and is completely independent. It builds all the container images
based on a configuration file passed to it using the Debian packaged version of the
service and a minimal image of a Debian based distro. A sample configuration is
provided in [example.json](/container-creator/example.json) which can be used as a
starting point for creating custom contests.
