"""IA Local Sandbox — intents auditadas, artifactory próprio, allowlist de fontes.

Regra de ouro: a IA só enxerga (1) o BD/serviços internos do sistema e
(2) as APIs que o usuário cadastrou (FonteDadosExterna ativas) + APIs padrão
do sistema (Open-Meteo). Qualquer outro destino é BLOQUEADO e registrado.
"""
