dictconfig
==========

A straightforward way of configuring a piece of Python software is to read
configuration settings from a file (usually JSON or YAML) into a Python
dictionary. While this is convenient, this approach has some limitations;
namely, fields within a JSON or YAML file cannot make use of variables, nor can
they reference one another.

`dictconfig` is a Python package that aims to ease these limitations by
supporting:

1. **External Variables**: Configuration values can reference external
   variables supplied by the program reading the configuration.
2. **Internal References**: The configuration can reference other settings
   within the same configuration.
3. **Domain-specific languages**: Custom parsers can be provided to convert
   configuration options to Python types in a domain-specific way. `dateconfig`
   comes with parsers for interpreting arithmetic expressions (e.g., `"(4 + 6) / 2"`),
   logical expressions (e.g., `"True and (False or True)"`), and relative datetimes
   (e.g., `"7 days after 2021-10-10"`).

See the full docs here: https://eldridgejm.github.io/dictconfig/
