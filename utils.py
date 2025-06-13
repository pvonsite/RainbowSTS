from typing import Any

from RealtimeTTS import EdgeEngine, SystemEngine

STT_MODELS = [
    'tiny',
    'tiny.en',
    'base',
    'base.en',
    'small',
    'small.en',
    'medium',
    'medium.en',
    'large-v1',
    'large-v2',
    'large-v3',
    'large',
    'distil-large-v2',
    'distil-medium',
    'larget-v3-turbo',
    'turbo',
]

TRANSLATE_MODELS = [
    {
        'name': 'facebook/m2m100_418M',
        'description': 'Multilingual translation model by Facebook, suitable for fast, moderate quality translations.',
        'supported': True,
    },
    {
        'name': 'facebook/m2m100_1.2B',
        'description': 'Larger multilingual translation model by Facebook, astonishing quality but slower.',
        'supported': True,
    },
    {
        'name': 'erax-ai/EraX-Translator-V1.0',
        'description': 'EraX-Translator, a high-quality translation model by EraX AI, optimized for Vietnamese but requires more resources.',
        'supported': False,
    }
]

TTS_SUPPORTED_ENGINES = [
    'edge',  # Edge TTS
    'system'
]

def match_language(voice_entry, language: str) -> bool:
    # Check if voice has atrribute 'locale' or 'language'
    if hasattr(voice_entry, 'locale'):
        return voice_entry.locale.startswith(language)
    elif hasattr(voice_entry, 'language'):
        return voice_entry.language.startswith(language)
    else:
        return True

def get_supported_voices(engine_name: str, language: str) -> list:
    _engine = None
    if engine_name == 'edge':
        _engine = EdgeEngine()
    elif engine_name == 'system':
        _engine = SystemEngine()
    else:
        raise ValueError(f'Unsupported engine name: {engine_name}')

    _voices = _engine.get_voices()

    if language:
        _voices = [voice for voice in _voices if match_language(voice, language)]

    return _voices

if __name__ == "__main__":
    # Example usage
    try:
        voices = get_supported_voices('system', 'vi')
        print(f"Supported voices for Edge TTS in English: {voices}")
    except Exception as e:
        print(f"Error: {e}")
