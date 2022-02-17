# challtools

challtools is a tool that manages CTF challenges and challenge repositories using the [OpenChallSpec](https://openchallspec.readthedocs.io/) challenge format.

## Installation

To install or upgrade challtools, use pip:

```
pip3 install --upgrade challtools
```

## Usage

### Initialization

challtools can initialize a directory with a challenge template for you. To get a template PHP challenge simply run:

```
$ challtools init php 
Directory initialized!
$ tree

├── challenge.yml
└── container
    ├── Dockerfile
    └── index.php

1 directory, 3 files
```

### Validating

challtools includes an [OpenChallSpec](https://openchallspec.readthedocs.io/) validator. To validate that a challenge complies with the spec, run `challtools validate` in the challenge directory:

```
$ challtools validate
No issues raised.
Validation succeeded. No issues detected!
```

### Building

challtools can build docker containers and run build scripts defined in the challenge config for you. Running `challtools build` with a container defined in the configuration will build that container:

```
$ challtools build
Flag: example{this_is_the_flag}
Processing container default...
Interpreting "container" as an image build directory
Building image...
Challenge built successfully!
```

Any solution containers will also be built in the same way.

challtools can also run custom build scripts, defined by adding something like this to the challenge config:

```yaml
custom:
  build_script: build.sh
```

This will run the `build.sh` file before any containers are built with the flag as a command line argument, allowing the flag to be inserted programmatically into the challenge. This eliminates any flag mismatches arising from the flag being defined in multiple places.

### Starting

challtools can start challenges for you. This is done by running `challtools start` in the challenge directory, with the optional `-b` flag to rebuild containers:

```
$ challtools start
Started container default
Services:
nc 127.0.0.1 50000
```

### Solving

If a challenge solution is defined, challtools can verify that the challenge is solvable by automatically solving it. It does this by first building the challenge, starting it, starting the solution docker container and checking for if it outputs a flag. This is done using `challtools solve`:

```
$ challtools solve
Started container default
Solving...
example{this_is_the_flag}

Challenge solved successfully!
```

### Other

challtools includes many other useful commands:

```
$ challtools --help
usage: challtools [-h] {allchalls,validate,build,start,solve,compose,ensureid,push,init,spoilerfree} ...

A tool for managing CTF challenges and challenge repositories using the OpenChallSpec

positional arguments:
  {allchalls,validate,build,start,solve,compose,ensureid,push,init,spoilerfree}
    allchalls           Runs a different command on every challenge in this ctf
    validate            Validates a challenge to make sure it's defined properly
    build               Builds a challenge by running its build script and building docker images
    start               Starts a challenge by running its docker images
    solve               Starts a challenge by running its docker images, and procedes to solve it using the solution container
    compose             Writes a docker-compose.yml file to the challenge directory which can be used to run all challenge services
    ensureid            Checks if a challenge has a challenge ID, and if not, generates and adds one
    push                Push a challenge to the ctf platform
    init                Initialize a directory with template challenge files
    spoilerfree         Pretty print challenge information available for participants, for test solving

options:
  -h, --help            show this help message and exit
```

## Autocompletion

challtools supports shell autocomplete through [argcomplete](https://github.com/kislyuk/argcomplete). To use it, either [activate global completion](https://github.com/kislyuk/argcomplete#activating-global-completion) or enable it manually for [bash](https://github.com/kislyuk/argcomplete#synopsis), [zsh](https://github.com/kislyuk/argcomplete#zsh-support) or [fish](https://github.com/kislyuk/argcomplete#fish-support) (remember to replace `my-awesome-script` with `challtools`).
