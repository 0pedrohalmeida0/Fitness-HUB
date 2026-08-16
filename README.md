# Fitness Hub

> Rede social fitness com diário alimentar, planos de dieta e feed social.

**Stack:** Flutter (mobile) · HTML/CSS/JS (site) · Python FastAPI (backend) · PostgreSQL/Neon · AWS S3

## Status

🚧 **MVP em desenvolvimento** — Fase 1: Auth (cadastro e login)

### O que já tem

- ✅ Schema do banco (PostgreSQL/Neon) — 9 tabelas
- ✅ Identidade visual (logo, paleta, tipografia)
- ✅ Telas de Login e Cadastro (HTML/CSS/JS)
- ✅ Backend de autenticação (FastAPI + JWT + bcrypt)
- ✅ Testes do fluxo de auth

### Próximos passos

- [ ] Home (perfil + grid de posts)
- [ ] Feed (timeline + likes + comentários)
- [ ] Dieta (registro diário + planos alimentares)
- [ ] App Flutter (mobile)
- [ ] Deploy (Neon + Railway/Render + Play Store)

## Estrutura do monorepo

```
fitness-hub/
├── frontend/          Site web (HTML/CSS/JS) — Login, Cadastro
├── backend/           API Python (FastAPI)
└── docs/              Documentação e brand
```

### Frontend (`/frontend`)

Site web responsivo com as telas de login e cadastro.

```bash
# Abrir direto no navegador
open frontend/login.html
```

Tecnologias: HTML5 semântico · CSS moderno (variáveis, flexbox, grid) · JS vanilla (Fetch API).

Para conectar com o backend, ajuste `API_BASE_URL` em `frontend/js/auth.js`.

### Backend (`/backend`)

API REST em FastAPI com SQLAlchemy async + Neon PostgreSQL.

```bash
cd backend
cp .env.example .env
# Edite DATABASE_URL com a connection string do Neon

# Docker (recomendado)
docker-compose up --build

# Ou local
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

**Endpoints do MVP:**

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/auth/register` | Criar conta |
| `POST` | `/auth/login` | Login (email ou username) |
| `POST` | `/auth/refresh` | Renovar token |
| `GET` | `/auth/me` | Usuário logado |
| `GET` | `/health` | Liveness check |

## Banco de dados

Schema em PostgreSQL com 9 tabelas: `usuarios`, `alimentos`, `meal_plans`, `meal_plan_items`, `alimentacao`, `post_media`, `follows`, `likes`, `comentarios`.

Inclui:
- Status de aprovação de alimentos (admin modera)
- Soft delete em posts e comentários
- Likes múltiplos por user (diferencial do app)
- Follow com status (pending/accepted/blocked) pra perfis privados

Aplicar no Neon: rode o SQL no painel ou use `alembic upgrade head` (depois de gerar a primeira migration com `alembic revision --autogenerate`).

## Identidade visual

- **Tagline:** Conecte-se. Treine. Evolua.
- **Cores:** Lime (#A3E635) + Violet (#7C3AED) sobre Ink (#0A0A0A)
- **Tipografia:** Outfit (UI) + JetBrains Mono (números)
- **Logo:** símbolo de rede formando a letra F

## Segurança

- Senhas com **bcrypt** (12 rounds, hash, nunca plain)
- **JWT** com access (1h) + refresh (7d)
- Validação rigorosa com Pydantic
- Mensagens genéricas no login (não vaza se user existe)
- CORS configurável por env

⚠️ **Em produção:**
- Trocar `JWT_SECRET` por uma chave aleatória (32+ chars): `openssl rand -hex 32`
- Mover tokens de `localStorage` pra cookies httpOnly
- Adicionar rate limit nos endpoints de auth
- Habilitar HTTPS obrigatório

## Testes

```bash
cd backend
pytest
```

Cobre 14 cenários do fluxo de auth (registro, login, /me, health, erros 401/409/422).

---

© 2026 Fitness Hub · Construído por [Pedro Almeida](https://github.com/0pedrohalmeida0)
