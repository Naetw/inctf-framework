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

## Components

The framework consists of several components. Some of them are new while some are
modifications of the corresponding components of the iCTF framework. See [component
descriptions](docs/components.md) for more information.

## Getting started

See [Setup and run a contest](docs/setup-and-run-a-contest.md) for a walkthrough on
how to get started.

## Writing a service

See [how to write a service](docs/writing-services.md).

## Writing an exploit

See [how to write an exploit](docs/writing-exploits.md).

## Further Information

Some details of the InCTF framework is described in our paper [Scalable and
Lightweight CTF Infrastructures Using Application
Containers](https://www.usenix.org/conference/ase16/workshop-program/presentation/raj)
published in [2016 USENIX Workshop on Advances in Security
Education](https://www.usenix.org/conference/ase16). The paper describes the high
level design and rationale behind the design choices.
