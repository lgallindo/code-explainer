import tomllib
from pathlib import Path

import google.generativeai as genai


def main():
    secrets_path = Path('.streamlit/secrets.toml')
    with secrets_path.open('rb') as f:
        secrets = tomllib.load(f)

    api_key = secrets['llm']['GEMINI_API_KEY']
    print(f'Using secrets from {secrets_path}')

    genai.configure(api_key=api_key)
    models = []
    for model in genai.list_models():
        methods = getattr(model, 'supported_generation_methods', []) or []
        name = getattr(model, 'name', '')
        if 'generateContent' in methods and name.startswith('models/gemini'):
            models.append(name.replace('models/', '', 1))

    models = sorted(set(models))
    print(f'Found {len(models)} Gemini models with generateContent')
    print()

    results = []
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content('Reply with exactly: ok')
            text = getattr(response, 'text', '')
            results.append((model_name, 'success', text[:120]))
            print(f'SUCCESS {model_name}: {text[:120]!r}')
        except Exception as exc:
            msg = str(exc).replace('\n', ' ')
            if '429' in msg or 'quota' in msg.lower() or 'rate limit' in msg.lower():
                status = 'quota'
            else:
                status = 'error'
            results.append((model_name, status, msg[:220]))
            print(f'{status.upper()} {model_name}: {msg[:220]}')

    successes = [r for r in results if r[1] == 'success']
    quota = [r for r in results if r[1] == 'quota']
    errors = [r for r in results if r[1] == 'error']

    print('\nSUMMARY')
    print(f'success={len(successes)} quota={len(quota)} error={len(errors)}')
    if successes:
        print('Models without 429:')
        for model_name, _, preview in successes:
            print(f'- {model_name}: {preview!r}')
    if quota:
        print('Models with 429/quota:')
        for model_name, _, preview in quota:
            print(f'- {model_name}: {preview}')
    if errors:
        print('Models with other errors:')
        for model_name, _, preview in errors:
            print(f'- {model_name}: {preview}')


if __name__ == '__main__':
    main()
