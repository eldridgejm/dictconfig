# Specification

The entry point to the library will be a function named `resolve()`. This
function will accept:

- `dct`: a dictionary of strings to be interpolated and parsed
- `schema`: a schema for the dictionary
- `context`: a dictionary of string values (or values convertible to strings)
  that may be interpolated into the values in `dct`

`resolve()` will *resolve* the strings in `dct` into Python values. Resolution
implies both *interpolation* and *parsing*. During interpolation of a string,
references to other variables are recursively resolved and their string value is
interpolated into the string being resolved. Next, the entire resulting string
is parsed according to the rule corresponding to the schema.

The resolution process proceeds as follows:

1. Construct a `NodeTree` representing the combination of `dct` and `schema`.
   This is a tree whose elements are either `InternalNode` objects
   (representing dicts or lists) or `LeafNode` objects (representing strings,
   integers, floats, etc). Each leaf node will have a `resolved` attribute
   containing the reolved value of the node as a Python object. 

   Leaf nodes will also carry a `type` attribute, inferred from the schema.
   If the path in `dct` does not appear in the schema, then the type will be
   assumed to be `string`. If a path in the schema does not appear in the `dct`,
   we'll have to decide what to do: raising an exception would reasonable.

2. A tree search is performed on the `NodeTree` in order to create a new
   dictionary of Python values. At each leaf node, the node's raw string is
   first interpolated (by recursively resolving the references nodes) and then
   parsed.
