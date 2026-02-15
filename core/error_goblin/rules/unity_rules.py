from __future__ import annotations

from typing import Optional


def match_unity_rule(text: str) -> Optional[dict]:
    t = (text or '').lower()

    if 'unassignedreferenceexception' in t:
        return {
            'summary': 'Inspector reference is unassigned',
            'what_it_means': 'A serialized field/property was used before assigning it in the inspector.',
            'likely_cause': 'Component/GameObject field left empty on prefab or scene instance.',
            'first_step': 'Open the object from the first script frame and assign all required serialized references.',
            'confidence': 0.93,
        }

    if 'nullreferenceexception' in t:
        return {
            'summary': 'Null reference access',
            'what_it_means': 'Code attempted to use an object reference that is null.',
            'likely_cause': 'Component/field not assigned in inspector, object destroyed, or lookup failed.',
            'first_step': 'Identify the first stack frame in your script and validate all references before use.',
            'confidence': 0.9,
        }

    if 'missingreferenceexception' in t:
        return {
            'summary': 'Reference points to destroyed object',
            'what_it_means': 'Unity object was destroyed but code still tries to use its reference.',
            'likely_cause': 'Object lifetime mismatch or cached reference used after Destroy().',
            'first_step': 'Find where the object is destroyed and clear/revalidate references before subsequent use.',
            'confidence': 0.9,
        }

    if 'argumentnullexception' in t:
        return {
            'summary': 'Null argument passed into API call',
            'what_it_means': 'A method received a null argument that it does not accept.',
            'likely_cause': 'Missing lookup result, optional value not checked, or uninitialized data.',
            'first_step': 'Inspect the argument named in the exception and guard/initialize it before calling the API.',
            'confidence': 0.89,
        }

    if 'argumentexception' in t:
        return {
            'summary': 'Invalid argument value',
            'what_it_means': 'A Unity/.NET API rejected one or more provided arguments.',
            'likely_cause': 'Out-of-range value, invalid path/name, or incompatible state for that call.',
            'first_step': 'Read the exception message for parameter details and validate inputs before invoking the call.',
            'confidence': 0.82,
        }

    if 'indexoutofrangeexception' in t:
        return {
            'summary': 'Index out of range',
            'what_it_means': 'An array/list index exceeded valid bounds.',
            'likely_cause': 'Collection size assumptions are wrong at runtime.',
            'first_step': 'Log collection length and index at the failing line, then add bounds checks.',
            'confidence': 0.88,
        }

    if 'missingcomponentexception' in t:
        return {
            'summary': 'Required component is missing',
            'what_it_means': 'Code expected a component that is not present on the target GameObject.',
            'likely_cause': 'Component was never added, removed, or requested from wrong object.',
            'first_step': 'Add/check the required component on the referenced GameObject or adjust lookup target.',
            'confidence': 0.9,
        }

    if ('couldn\'t be loaded because it has not been added to the build settings' in t) or (
        'scene \'' in t and 'couldn\'t be loaded' in t
    ):
        return {
            'summary': 'Scene failed to load',
            'what_it_means': 'SceneManager could not load the requested scene name/path.',
            'likely_cause': 'Scene missing from Build Settings, typo in scene name, or wrong address/path.',
            'first_step': 'Confirm scene name matches exactly and that it is included in Build Settings.',
            'confidence': 0.9,
        }

    if 'the object of type' in t and 'has been destroyed but you are still trying to access it' in t:
        return {
            'summary': 'Access to destroyed Unity object',
            'what_it_means': 'A destroyed UnityEngine.Object reference is being used later.',
            'likely_cause': 'Destroyed lifecycle object still cached by system/listener.',
            'first_step': 'Null-check before access and unsubscribe/clear cached references when object is destroyed.',
            'confidence': 0.9,
        }

    return None
