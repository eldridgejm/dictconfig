schema = {
        'name': {
            'type': 'dict'
            'schema': {
                'first': {'type': 'string'},
                'last': {'type': 'string'},
            }
        },
        'full_name': {'type': 'string'},
        'number': {'type': 'integer'},
        }


data = {
    'name': {'first': 'Justin', 'last': 'Eldridge'},
    'full_name': '${self.name.first} ${self.name.last}',
    'number': '5 + 2',

}


>>> resolve(data, schema)
{
    'name': {'first': 'Justin', 'last': 'Eldridge'},
    'full_name': 'Justin Eldridge',
    'number': 7
}

