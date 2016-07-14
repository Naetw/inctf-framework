# Components

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
