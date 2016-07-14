# The InCTF Framework

This framework forms the basis of the game infrastructure used to run the
attack-defence round of InCTF organized annually by [Amrita
University](https://amrita.edu/) and [Amrita Centre for Cybersecurity Systems and
Networks](https://amrita.edu/cyber/). It is based on the [iCTF
framework](https://github.com/ucsb-seclab/ictf-framework/) released by UC Santa
Barbara Seclab. Unlike the iCTF framework, this framework runs all services in Docker
containers instead of virtual machines. In addition, this framework also runs
exploits uploaded by teams as Docker containers. This reduces the amount of resources
required by the game infrastructure. Additionally, the use of additional tools such
as Docker distribution and PORTUS simplifies setting up the game infrastructure and
gameplay for participants.

The framework consists of several components. Some of them are new while some are
modifications of the corresponding components of the iCTF framework.

## Central Database

This is the central database that tracks the game state and state of the service and
exploit container images. It runs on the organizer machine and exposes a REST API,
which is used by other components.

## Container creator

This is the container creator that is used to build and upload the service container
images to the container image registry. This replaces the vmcreator component of the
iCTF framework.

## Container registry

The registry manages all service container and exploit container images of all teams.
It is a combination of [Docker distribution](https://docs.docker.com/registry/) and
[PORTUS](http://port.us.org/). This is a new component of the game infrastructure and
consists of third party tools.

## Dashboard

This is the CTF dashboard, showing the scoreboard and status of services and allowing
players to submit flags. The backend of this component was rewritten in Python.
Read the [docs](dashboard/README.md).

## Gamebot

The gamebot initiates a new round of the contest and also handles synchronizing the
live containers with their corresponding container images.

## Scorebot

In addition to updating flags on the vulnerable services and checking that the flags
are accessible, the scorebot also runs the exploit containers created by teams.

## Services

The InCTF Framework extends the standard format for creating services laid out by the
iCTF framework by adding few new fields. Services live in the services/ directory.

## Further Information

Some details of the InCTF framework is described in our paper [Scalable and
Lightweight CTF Infrastructures Using Application
Containers](https://www.usenix.org/conference/ase16/workshop-program/presentation/raj)
published in [2016 USENIX Workshop on Advances in Security
Education](https://www.usenix.org/conference/ase16). The paper describes the high
level design and rationale behind the design choices.
