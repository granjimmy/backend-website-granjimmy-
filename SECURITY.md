# Segurança e privacidade

Este backend deve ser tratado como sistema administrativo. O Git armazena somente código e exemplos sem credenciais.

## Dados proibidos

Nunca enviar ao Git:

- dados de pacientes, familiares, atendimentos ou prontuários;
- base real de inscritos da newsletter;
- bancos de dados, dumps, backups, logs ou diretórios `media/`;
- senhas, tokens, chaves privadas, cookies, arquivos `.env` ou credenciais SMTP;
- fotos e documentos sem base legal, autorização e finalidade institucional validadas.

Copie `.env.example` para `.env` apenas no ambiente local/servidor. Em produção, use um gerenciador de segredos, privilégio mínimo, TLS, backups criptografados e acesso auditável.

## Relato de vulnerabilidade

Não abra issue pública com detalhes exploráveis ou dados pessoais. Comunique o responsável técnico da organização por canal privado, usando o mínimo de dados necessário.
