from __future__ import annotations

from typing import Optional


def match_python_rule(text: str) -> Optional[dict]:
    t = (text or '').lower()

    if 'modulenotfounderror:' in t or 'importerror:' in t:
        return {
            'summary': 'Import failed for module/package',
            'what_it_means': 'Python could not import a required module.',
            'likely_cause': 'Dependency not installed, wrong virtual environment, or import path/module name mismatch.',
            'first_step': 'Check the exact module name in the traceback and verify it is installed in the active interpreter.',
            'confidence': 0.92,
        }

    if 'syntaxerror:' in t or 'indentationerror:' in t:
        return {
            'summary': 'Syntax or indentation error',
            'what_it_means': 'Python parser failed before runtime due to invalid code structure.',
            'likely_cause': 'Missing bracket/colon/quote or inconsistent indentation.',
            'first_step': 'Open the file/line in the traceback and fix the first reported parser error before rerunning.',
            'confidence': 0.93,
        }

    if 'attributeerror:' in t:
        return {
            'summary': 'Missing attribute or method',
            'what_it_means': 'Code accessed an attribute that does not exist on that object.',
            'likely_cause': 'Type mismatch at runtime, typo in attribute name, or outdated API usage.',
            'first_step': 'Inspect the object type/value at the failing line and compare against expected API members.',
            'confidence': 0.9,
        }

    if 'nameerror:' in t:
        return {
            'summary': 'Name is not defined',
            'what_it_means': 'Code referenced a variable/function/class that is not in scope.',
            'likely_cause': 'Typo, missing import, or use before assignment/definition.',
            'first_step': 'Check spelling and scope for the missing name and confirm required imports run first.',
            'confidence': 0.92,
        }

    if 'keyerror:' in t:
        return {
            'summary': 'Dictionary key is missing',
            'what_it_means': 'Code accessed a dict key that does not exist.',
            'likely_cause': 'Input data shape changed, key typo, or key was never populated.',
            'first_step': 'Check dict.keys() near the failing line and use get()/in guards where appropriate.',
            'confidence': 0.9,
        }

    if 'indexerror:' in t:
        return {
            'summary': 'Index is out of range',
            'what_it_means': 'Code tried to access a list/sequence position that does not exist.',
            'likely_cause': 'Unexpected list length or loop/index math issue.',
            'first_step': 'Print the sequence length and index before access, then guard bounds.',
            'confidence': 0.88,
        }

    if 'noneType'.lower() in t and 'typeerror:' in t:
        return {
            'summary': 'Operation used None where a value was expected',
            'what_it_means': 'A None value is being used in an operation that requires another type.',
            'likely_cause': 'Missing return path, failed lookup, or optional value not checked.',
            'first_step': 'Trace where the variable is set and add explicit None checks before use.',
            'confidence': 0.86,
        }

    if 'filenotfounderror:' in t:
        return {
            'summary': 'File path does not exist',
            'what_it_means': 'Python could not open/read a file at the specified path.',
            'likely_cause': 'Wrong working directory, typo, or file not generated yet.',
            'first_step': 'Log the absolute path and confirm it exists before opening.',
            'confidence': 0.92,
        }

    if 'permissionerror:' in t:
        return {
            'summary': 'File or resource permission denied',
            'what_it_means': 'Python tried to read/write/execute something without required permissions.',
            'likely_cause': 'Protected path, file lock, or insufficient OS/user permissions.',
            'first_step': 'Check the exact path/resource in the traceback and retry with a writable location/permissions.',
            'confidence': 0.9,
        }

    if 'valueerror:' in t and 'invalid literal for int()' in t:
        return {
            'summary': 'Invalid string converted to integer',
            'what_it_means': 'Code attempted int() conversion on non-numeric text.',
            'likely_cause': 'Unexpected input format, empty value, or untrimmed characters.',
            'first_step': 'Log the raw input before int() and add validation/strip/default handling.',
            'confidence': 0.9,
        }

    if 'jsondecodeerror:' in t:
        return {
            'summary': 'JSON parse failed',
            'what_it_means': 'Input is not valid JSON at the reported position.',
            'likely_cause': 'Malformed JSON, trailing commas, wrong encoding, or partial file content.',
            'first_step': 'Validate the JSON near the reported line/column and confirm file encoding/contents.',
            'confidence': 0.9,
        }

    if 'assertionerror:' in t:
        return {
            'summary': 'Assertion failed',
            'what_it_means': 'An assert condition evaluated to False.',
            'likely_cause': 'Unexpected program state or stale assumptions in code/tests.',
            'first_step': 'Inspect the assertion expression inputs and verify the expected invariant at runtime.',
            'confidence': 0.85,
        }

    if 'typeerror:' in t:
        return {
            'summary': 'Type mismatch in operation or call',
            'what_it_means': 'An operation received a value of the wrong type.',
            'likely_cause': 'Unexpected runtime data shape or argument order mismatch.',
            'first_step': 'Log the involved values and types at the failing call site.',
            'confidence': 0.78,
        }

    return None
