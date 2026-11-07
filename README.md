# Chalé Viçosa — Gerenciador de Aluguel por Diária

App web em Python (stdlib) para gerenciar aluguel por diária (R$400–450), com cadastro por e-mail, reservas, liberação de senha da fechadura digital Kuanttum Pro e relatórios. Integração com Google Agenda via exportação de evento (ICS) / link de calendário.

## Como rodar
```bash
cd rental-app
python app.py
```
Acesse http://localhost:8000

Admin padrão: admin@chalevicosa.com / admin123 (troque em produção).

## Segurança
- Senhas com salt + SHA-256 (PBKDF2 recomendado em produção).
- Sessões com token aleatório e expiração de 8h.
- Troque a senha do admin no primeiro acesso.

## Criador
Yuri Gomes Junior — Instagram @yuripiaui

## Integrações
- Google Agenda: gere link ICS por reserva (endpoint a implementar) ou use OAuth Google Calendar API com credenciais.
- Fechadura Kuanttum Pro: código temporário gerado por reserva; integre com API do fabricante para envio automático.
""">
path">
rental-app/README.md