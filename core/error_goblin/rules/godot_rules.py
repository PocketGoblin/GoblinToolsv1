from __future__ import annotations

from typing import Optional


def match_godot_rule(text: str) -> Optional[dict]:
    t = (text or '').lower()

    if 'parse error' in t or 'parser error' in t:
        return {
            'summary': 'GDScript parser error',
            'what_it_means': 'Godot could not parse the script before runtime.',
            'likely_cause': 'Syntax issue such as missing colon/bracket, invalid indentation, or malformed expression.',
            'first_step': 'Fix the first parser error shown in the output panel, then rerun to reveal any follow-on errors.',
            'confidence': 0.93,
        }

    if 'script inherits from native type' in t and 'can\'t be assigned' in t:
        return {
            'summary': 'Script type does not match assigned node',
            'what_it_means': 'A script was attached where its declared base type is incompatible.',
            'likely_cause': 'extends type mismatch after refactor or attaching script to wrong node type.',
            'first_step': 'Compare script extends class with the target node type and reattach to a compatible node.',
            'confidence': 0.9,
        }

    if 'invalid get index' in t:
        return {
            'summary': 'Invalid get index on a value',
            'what_it_means': 'The script tried to access a property or key that does not exist on the current value.',
            'likely_cause': 'Typo in a key/property, or variable type is not what you expect at runtime.',
            'first_step': 'Print the variable type/value right before the failing line and verify the key/property exists.',
            'confidence': 0.9,
        }

    if 'invalid set index' in t:
        return {
            'summary': 'Invalid set index on a value',
            'what_it_means': 'The script tried to assign a property/key that does not exist on the target value.',
            'likely_cause': 'Wrong object/dictionary shape at runtime or typo in property/key name.',
            'first_step': 'Log target type/value before assignment and verify the property/key is valid for that type.',
            'confidence': 0.9,
        }

    if 'attempt to call function' in t and ('base nil' in t or 'null instance' in t):
        return {
            'summary': 'Function called on a null/Nil object',
            'what_it_means': 'The instance was null when you tried to call a method on it.',
            'likely_cause': 'Node/reference was never assigned, freed earlier, or get_node lookup failed.',
            'first_step': 'Add a null check before the call and log when/where the reference is assigned.',
            'confidence': 0.92,
        }

    if 'nonexistent function' in t:
        return {
            'summary': 'Method does not exist on target object',
            'what_it_means': 'A function call was made to a method that the object does not implement.',
            'likely_cause': 'Method rename/signature mismatch, wrong object type, or stale script attachment.',
            'first_step': 'Confirm object type and method name at the failing line, then sync call sites with current API.',
            'confidence': 0.9,
        }

    if 'method not found' in t and 'signal' in t:
        return {
            'summary': 'Connected signal target method missing',
            'what_it_means': 'A signal emitted to a method name that does not exist on the receiver.',
            'likely_cause': 'Method renamed/deleted or stale signal connection in scene.',
            'first_step': 'Open node signal connections and update/recreate the connection to an existing method.',
            'confidence': 0.88,
        }

    if ('node not found' in t) or ('get_node' in t and 'not found' in t):
        return {
            'summary': 'Node path lookup failed',
            'what_it_means': 'The scene tree path used by get_node/get_node_or_null did not resolve.',
            'likely_cause': 'Path mismatch, renamed node, wrong scene hierarchy, or call happening before node exists.',
            'first_step': 'Verify the exact node path in the running scene and prefer exported NodePath where possible.',
            'confidence': 0.88,
        }

    if 'cannot call method' in t and 'on a null value' in t:
        return {
            'summary': 'Method call on null value',
            'what_it_means': 'A method invocation target is null at runtime.',
            'likely_cause': 'Lookup failed, freed node, or dependency not initialized yet.',
            'first_step': 'Guard the call with null checks and trace assignment lifecycle of that reference.',
            'confidence': 0.9,
        }

    if 'resource file not found' in t or 'can\'t open' in t and 'res://' in t:
        return {
            'summary': 'Resource path could not be loaded',
            'what_it_means': 'Godot failed to load a resource/script/scene at the given path.',
            'likely_cause': 'Moved/renamed file, wrong path casing, or export/import mismatch.',
            'first_step': 'Verify the exact `res://` path exists and reassign references in inspector if needed.',
            'confidence': 0.89,
        }

    return None
