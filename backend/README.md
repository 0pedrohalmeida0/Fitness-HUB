# Fitness Hub — Backend

API REST em FastAPI com SQLAlchemy async + Neon PostgreSQL.

## Stack

- **Python 3.11+**
- **FastAPI** — web framework
- **SQLAlchemy 2.0 async** + **asyncpg** — ORM async
- **Pydantic v2** — validação
- **passlib[bcrypt]** — hash de senha
- **python-jose** — JWT
- **Alembic** — migrations
- **slowapi** — rate limiting
- **Neon** — PostgreSQL serverless (produção)

## Estrutura

```
backend/
├── app/
│   ├── core/           # config, db, security, dependencies
│   ├── models/         # SQLAlchemy models
│   ├── schemas/        # Pydantic schemas
│   ├── routers/        # endpoints HTTP
│   ├── services/       # lógica de negócio
│   └── main.py         # app FastAPI
├── alembic/            # migrations
├── tests/              # testes pytest
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

## Setup local

### Opção 1: Docker (recomendado)

```bash
cd backend
cp .env.example .env
docker-compose up --build
```

A API fica em `http://localhost:8000`.
Docs interativas em `http://localhost:8000/docs`.

### Opção 2: Local sem Docker

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

pip install -r requirements.txt
cp .env.example .env
# Edite o .env com a DATABASE_URL do Neon (ou use Postgres local)

uvicorn app.main:app --reload
```

## Endpoints disponíveis (MVP auth)

| Método | Rota          | Descrição                       | Auth |
|--------|---------------|---------------------------------|------|
| POST   | `/auth/register` | Criar conta nova              | -    |
| POST   | `/auth/login`    | Login (email ou username)     | -    |
| POST   | `/auth/refresh`  | Renovar access token          | -    |
| GET    | `/auth/me`       | Dados do usuário logado       | ✅   |
| POST   | `/auth/logout`   | Logout (stateless)            | -    |
| GET    | `/health`        | Liveness check                | -    |
| GET    | `/ready`         | Readiness check (com DB)      | -    |
| GET    | `/`              | Info da API                    | -    |
| GET    | `/docs`          | Swagger UI                     | -    |

## Banco de dados (Neon)

1. Crie um projeto no [Neon](https://neon.tech)
2. Pegue a connection string (com pooling)
3. Cole no `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.sa-east-1.aws.neon.tech/fitnesshub?ssl=require
   ```
4. Aplique o schema (uma das duas opções):
   - **Manualmente**: rode o `schema.sql` no painel SQL do Neon
   - **Com Alembic**: `alembic upgrade head` (depois de gerar a primeira migration)

### Gerar a primeira migration

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

## Segurança implementada

✅ Senha com bcrypt (12 rounds) — nunca plain
✅ JWT com access (1h) + refresh (7d)
✅ Validação rigorosa com Pydantic (regex, min/max, EmailStr)
✅ Mensagens genéricas no login (não vaza se user existe)
✅ CORS configurável via env
✅ Rate limiting via slowapi
✅ Tokens via HTTPBearer (Authorization: Bearer ...)

## Próximos passos

Os models/endpoints abaixo já estão mapeados no plano, mas ainda não foram implementados:

- [ ] `users` (PATCH /users/me, GET /users/{username})
- [ ] `follows` (POST/DELETE/PATCH /follows/{user_id})
- [ ] `posts` (POST/GET/DELETE /posts, GET /feed)
- [ ] `likes` (POST /posts/{id}/like — múltiplos permitidos)
- [ ] `comments` (POST/GET/DELETE)
- [ ] `alimentos` (com aprovação de admin)
- [ ] `alimentacao` (registro diário)
- [ ] `meal_plans` + `meal_plan_items`
- [ ] Upload S3 com presigned URL

## Testes

```bash
pytest
```

Cobre: registro, login (com email/username), erros 401/409/422, `/auth/me`, health.

## Variáveis de ambiente

Veja `.env.example`. Em produção, **sempre** troque o `JWT_SECRET` por uma chave random forte (32+ chars).

```bash
# Gera uma chave aleatória
openssl rand -hex 32
```
