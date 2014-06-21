# clrenv

A tool to give easy access to environment yaml file to python.

## Getting Started

* Install clrenv
```
$ pip install git+https://git+https://github.com/ColorGenomics/clrenv.git@v0.1.0
```

* Create a file called `environment.yaml`.
```
# environment.yaml
base:
  name: foo
  location: sf
```

* Set a path to the file.
```
$ export CLRENV_PATH=/path/to/environment.yaml
```

* Access env varianble from python
```
> from clrenv import env
> env.name
=> "foo"
> env.location
=> "sf"
```

## Add a mode

* Edit the `environment.yaml` file.
```
# environment.yaml
base:
  name: foo
  location: sf

production:
  location: nyc
```

* Set a mode:
```
$ export CLRENV_MODE=production
```

* Access env varianble from python
```
> from clrenv import env
> env.name
=> "foo"
> env.location
=> "nyc"
```

## Add an overlay

* Create a file called `environment.overlay.yaml`.
```
# environment.overlay.yaml
base:
  name: bar
```

* Set a path to the file.
```
$ export CLRENV_OVERLAY_PATH=/path/to/environment.overlay.yaml
```

* Access env varianble from python
```
> from clrenv import env
> env.name
=> "bar"
> env.location
=> "sf"
```
