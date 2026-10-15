"""Selecção de culturas por propriedade.

`app.cultures.seletor` é o único sítio que sabe transformar a tabela global
`Cultura` na lista que o produtor vê no cadastro da propriedade. Existe para
que a view (`app/views/auth.py::onboarding_view`) e o template
(`onboarding.html`) dependam do MESMO formato — a divergência entre os dois
já custou um bug antes (ver `app/tests_onboarding.py`).
"""
