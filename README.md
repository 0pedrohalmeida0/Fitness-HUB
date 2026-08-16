# Fitness Hub

> Rede social fitness com diário alimentar, planos de dieta e feed social.

**Stack:** Flutter (mobile) · HTML/CSS/JS (site) · Python FastAPI (backend) · PostgreSQL/Neon · AWS S3

## Status

🚧 **MVP em desenvolvimento**

### Implementado

- ✅ Schema do banco (PostgreSQL/Neon) — 9 tabelas
- ✅ Identidade visual (logo, paleta, tipografia)
- ✅ Telas de Login e Cadastro (HTML/CSS/JS)
- ✅ Backend de autenticação (FastAPI + JWT + bcrypt)
- ✅ Módulo Dieta (catálogo + log diário + admin approval)

### Próximos passos

- [ ] Home (perfil + grid de posts)
- [ ] Feed (timeline + likes + comentários)
- [ ] App Flutter (mobile)
- [ ] Deploy (Neon + Railway/Render + Play Store)

## Estrutura do monorepo

```
fitness-hub/
├── frontend/          Site web (HTML/CSS/JS)
│   ├── login.html
│   ├── register.html
│   ├── dieta.html
│   ├── css/
│   └── js/
└── backend/           API Python (FastAPI)
    ├── app/
    ├── alembic/
    ├── tests/
    ├── requirements.txt
    ├── .env.example
    ├── alembic.ini
    ├── pytest.ini
    ├── Dockerfile
    └── docker-compose.yml
```

## Módulos do backend

| Módulo     | Rotas                                       | Status |
|------------|---------------------------------------------|--------|
| Auth       | `/auth/*`                                   | ✅      |
| Alimentos  | `/alimentos/*`                              | ✅      |
| Alimentação| `/alimentacao/*`                            | ✅      |
| Posts      | `/posts/*`                                  | ⏳      |
| Follows    | `/follows/*`                                | ⏳      |
| Likes      | `/posts/{id}/like`                          | ⏳      |
| Comentários| `/posts/{id}/comments`                      | ⏳      |
| Meal Plans | `/meal-plans/*`                             | ⏳      |

## Frontend

Pura HTML/CSS/JS (vanilla). Sem build step.

- `login.html` / `register.html` — autenticação
- `dieta.html` — módulo Dieta (catálogo + log diário + submeter alimento)

Pra rodar: abra os HTMLs direto no navegador, ou sirva com qualquer static server (`python -m http.server`, `npx serve`, etc).

Pra conectar com backend, ajuste `API_BASE_URL` em `frontend/js/api.js`.

## Backend

FastAPI + SQLAlchemy async + Neon.

```bash
cd backend
cp .env.example .env
# Editar DATABASE_URL com connection string do Neon

# Docker (recomendado)
docker-compose up --build

# Ou local
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: `http://localhost:8000` · Docs: `http://localhost:8000/docs`

## Endpoints do MVP

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| `POST` | `/auth/register` | Criar conta | - |
| `POST` | `/auth/login` | Login (email ou username) | - |
| `POST` | `/auth/refresh` | Renovar token | - |
| `GET` | `/auth/me` | Usuário logado | ✅ |
| `GET` | `/alimentos` | Listar aprovados (com busca) | - |
| `POST` | `/alimentos` | Criar (vai pra pending) | ✅ |
| `GET` | `/alimentos/pending` | Pendentes (admin only) | ✅ |
| `PATCH` | `/alimentos/{id}/approve` | Aprovar (admin only) | ✅ |
| `PATCH` | `/alimentos/{id}/reject` | Rejeitar (admin only) | ✅ |
| `POST` | `/alimentacao` | Registrar consumo | ✅ |
| `GET` | `/alimentacao?data=YYYY-MM-DD` | Lista do dia | ✅ |
| `GET` | `/alimentacao/resumo?data=YYYY-MM-DD` | Resumo nutricional | ✅ |
| `DELETE` | `/alimentacao/{id}` | Remover (soft delete) | ✅ |
| `GET` | `/health` | Liveness check | - |
| `GET` | `/ready` | Readiness (testa DB) | - |

## Banco de dados

Schema em PostgreSQL com 9 tabelas: `usuarios`, `alimentos`, `meal_plans`, `meal_plan_items`, `alimentacao`, `post_media`, `follows`, `likes`, `comentarios`.

Fluxo do Alimento: user cria → status='pending' → admin aprova → status='approved' → outros users podem usar no log.

## Testes

```bash
cd backend
pytest
```

27 cenários cobrindo auth (14) + dieta (13).

## Segurança

- Senhas com **bcrypt** (12 rounds)
- **JWT** com access (1h) + refresh (7d)
- Validação rigorosa com Pydantic
- Mensagens genéricas no login
- CORS configurável
- Soft delete em alimentacao, post_media, comentarios

⚠️ **Em produção:**
- Trocar `JWT_SECRET` por uma chave aleatória (32+ chars): `openssl rand -hex 32`
- Mover tokens de `localStorage` pra cookies httpOnly
- Habilitar HTTPS obrigatório

---

© 2026 Fitness Hub
