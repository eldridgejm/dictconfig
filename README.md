dictconfig
==========


`dictconfig` is a Python library that makes it more convenient to use dictionaries
for program configuration.

The three main features of `dictconfig` are:

- **Validation**: Dictionaries can be validated to ensure that required keys
  are provided and their values have the right type, and missing optional
  values are replaced with defaults.
- **Interpolation**: Configuration values can reference other parts of the
  configuration, or even external variables supplied by the user. This allows
  for configuration following the DRY ("Don't Repeat Yourself") principle.
- **Calculations**: Configuration values can be computed from expressions.
  Built-in parsers are provided to do simple arithmetic on numbers and dates,
  as well as logical operations on booleans. Custom parsers can be added to
  handle other types.

See the full docs here: https://eldridgejm.github.io/dictconfig/

Demo
----

The following toy example demonstrates the core features of `dictconfig`. Consider
the YAML configuration file below:

```yaml
release-date: 2025-01-10
due: 7 days after ${this.release-date}
x: 10
y: 3
z: 2 * ${this.x} + ${this.y}
```

Notice that some of the fields in this configuration file contain references to
other fields and are calculated based on these references. For example, we'd
like the eventual value of `due` to be `2025-01-17` (i.e., 7 days after the
value of `release-date`).

Of course, if we read this YAML into a Python dictionary using any standard
YAML loader, the result will be the below dictionary, where the values of each
field are simply the literal values from the YAML file:


```
{
   'release-date': '2025-01-10',
   'due': '7 days after ${this.release-date}',
   'x': 10,
   'y': 3,
   'z': '2 * ${this.x} + ${this.y}'
}
```

`dictconfig` takes this dictionary as input and "resolves" references and calculated
values to obtain the following dictionary:

```
{
   'release-date': datetime.date(2025, 1, 10),
   'due': datetime.date(2025, 1, 17),
   'x': 10,
   'y': 3,
   'z': 23
}
```
