# Granjimmy — Backend (Django + PostgreSQL)

API e painel editorial do Granjimmy Hospital Psiquiátrico.
Substitui o backend PocketBase anteriormente utilizado pelo projeto.

- **API pública:** consumida pelo frontend (Vercel)
- **Painel `/painel/`:** onde os médicos escrevem, agendam e publicam
- **Newsletter:** avisa os inscritos quando sai publicação nova

## Subir localmente

```bash
cp .env.example .env      # gere uma DJANGO_SECRET_KEY e defina POSTGRES_PASSWORD
docker compose up -d --build
docker compose exec api python manage.py criar_grupos
docker compose exec api python manage.py createsuperuser
```

Painel em http://localhost:8000/painel/ · API em http://localhost:8000/api/v1/

## Fluxo editorial

| Situação | Quem define | Aparece no site? |
|---|---|---|
| **Rascunho** | médico | não |
| **Agendado** | médico (com data futura) | só quando a data chega |
| **Publicado** | apenas editor | sim |

O médico **não publica direto**: escolhe Rascunho ou Agendado, e o post vai
para revisão. Só quem está no grupo *Editores* publica.

O agendamento não depende de worker: `Post.objects.published()` filtra por
`published_at <= agora`, então o post entra no ar sozinho. O comando abaixo
normaliza o status e dispara a newsletter.

### Cron (obrigatório para a newsletter)

```cron
* * * * * cd /opt/granjimmy-backend && docker compose exec -T api python manage.py publicar_agendados >> /var/log/granjimmy-cron.log 2>&1
```

Teste sem enviar nada: `--dry-run`. Publicar sem notificar: `--no-email`.

## Cadastrar um médico

1. `/painel/` → **Usuários** → adicionar, marcar **Membro da equipe** (`is_staff`)
2. Adicionar ao grupo **Médicos**
3. **Blog → Autores** → criar o perfil e vincular à conta criada
   (nome de exibição, CRM, especialidade e **foto** — a foto aparece no card do post)

Sem o perfil de Autor vinculado, o médico é avisado ao tentar salvar.

## Permissões

| Ação | Médico | Editor |
|---|---|---|
| Criar/editar publicação própria | sim | sim |
| Ver/editar de outro autor | **não** | sim |
| Editar post já publicado | **não** (somente leitura) | sim |
| Publicar / despublicar | **não** | sim |
| Escolher o autor da publicação | **não** (é sempre ele) | sim |
| Ver base de inscritos | **não** (LGPD) | sim |

As travas estão em `blog/admin.py` e valem no **servidor**, não só na tela:
`get_queryset`, `save_model` e `has_change_permission` barram POST forjado.

## Testes

```bash
docker compose exec api python manage.py test
```

21 testes cobrindo o fluxo editorial (rascunho/agendamento/publicação,
idempotência da newsletter), as travas de permissão do médico (com POST
forjado, não só a interface) e os contratos da API.

**Alterou código? `docker compose up -d --build api`** — o código vai para
dentro da imagem, então `restart` sozinho não aplica a mudança.

## API

| Rota | Descrição |
|---|---|
| `GET /api/v1/posts/` | lista paginada (só publicados e no ar) |
| `GET /api/v1/posts/<slug>/` | detalhe com conteúdo e tags |
| `GET /api/v1/categorias/` · `/tags/` · `/autores/` | apoio |
| `POST /api/v1/newsletter/inscrever` | `{email, name}` → 202 |
| `GET /api/v1/newsletter/confirmar/<token>` | double opt-in |
| `GET /api/v1/newsletter/descadastro/<token>` | descadastro |
| `GET /api/health` | healthcheck |

Filtros: `?category__slug=`, `?author__slug=`, `?search=`, `?ordering=-published_at`

O card traz exatamente o pedido: **título, imagem, breve descrição, data,
autor e foto do autor**.

```json
{
  "title": "...", "excerpt": "...", "cover_image": "http://.../blog/x.jpg",
  "published_at": "2026-08-06T12:30:11-04:00",
  "author": {"display_name": "Dr. Miler Nunes Soares",
             "credential": "CRM-MT 4687 / RQE 2756",
             "photo": "http://.../autores/miler.jpg"}
}
```

## Produção

- `DJANGO_DEBUG=False` e `DJANGO_SECRET_KEY` forte (obrigatórios)
- `API_BIND=127.0.0.1` — a API só responde via proxy reverso (Caddy/nginx) com TLS
- O Postgres **não** expõe porta: só a rede interna do compose alcança
- `CORS_ALLOWED_ORIGINS` = domínio da Vercel; `CSRF_TRUSTED_ORIGINS` = domínio da API
- Com `DEBUG=False`, HSTS, cookies `Secure` e redirect HTTPS entram automaticamente
- Backup: `docker compose exec db pg_dump -U granjimmy granjimmy | gzip > backup.sql.gz`

`media/` (imagens enviadas) é volume Docker — inclua no backup.

## Pendências

- `$ai`: chat e busca semântica (o `pgvector/pgvector:pg16` já está no compose)
- Migrar o conteúdo real do PocketBase
- Servir `media/` por CDN/S3 quando o volume crescer
