# 🗺️ Plano de Ação — Fitness Hub MVP

# Visão Geral
Stack: Flutter (Dart) + FastAPI (Python) + Neon (PostgreSQL) + AWS S3
MVP: 3 abas — Home, Feed, Dieta

Fase 1 — Fundação 
1.1 Repositório & Ambiente
[ ] Criar monorepo (/frontend, /backend, /infra) ou repos separados
[ ] .gitignore, README.md com instruções de setup
[ ] Docker Compose local (PostgreSQL + MinIO como S3 local) — não depende do Neon ainda
[ ] CI/CD básico (GitHub Actions: lint + testes nos PRs)
1.2 FastAPI setup
[ ] Estrutura de pastas: app/routers, app/models, app/services, app/core, app/schemas
[ ] requirements.txt: fastapi, uvicorn, sqlalchemy, psycopg2-binary, alembic, python-jose, passlib, boto3, pydantic-settings, python-multipart
[ ] Configuração por ambiente (.env): DATABASE_URL, S3_*, JWT_SECRET, ALGORITHM
[ ] Conexão com Neon via SQLAlchemy async (asyncpg) — Neon é serverless, conexões são caras, usar pool pequeno
[ ] Alembic configurado para migrations
[] CORS, estrutura para presigned URL, slowapi instalado
1.3 Frontend — Setup Flutter
[ ] flutter create com estrutura limpa
[ ] Pastas: lib/core/, lib/features/, lib/shared/
[ ] Gerenciamento de estado: Riverpod (recomendo) ou Bloc — decida agora
[ ] HTTP client: dio + interceptors (token, refresh, logs)
[ ] .env com API_BASE_URL, S3_BASE_URL
1.4 AWS S3 Setup
[ ] Criar bucket na região mais próxima (São Paulo = sa-east-1)
[ ] Política IAM: upload direto do backend (presigned URL é melhor para mobile, mas pro MVP, upload pelo backend é mais simples)
[ ] CORS configurado no bucket para aceitar o domínio do app futuro
Fase 2 — Backend Core 
2.1 Autenticação (JWT)
[ ] Registro: POST /auth/register (username, email, senha, nome_completo)
[ ] Login: POST /auth/login → retorna access_token + refresh_token
[ ] Middleware de proteção de rotas (Depends(get_current_user))
[ ] Hash de senha com bcrypt
[ ] Decisão: Refresh token salvo no banco (tabela refresh_tokens) ou stateless? Pro MVP, stateless com expiração longa (7 dias) é aceitável.
2.2 Models SQLAlchemy
[ ] Mapear todas as 9 tabelas do schema v1.1
[ ] Relacionamentos: User.posts, User.follows, PostMedia.likes, PostMedia.comments, etc.
[ ] Soft delete implementado nos models (filtro automático nas queries)
2.3 Upload de Mídia
[ ] Endpoint POST /upload → recebe arquivo, envia para S3, retorna URL
[ ] Validação: tipo (jpg, png, mp4), tamanho máximo (10MB), ratio (opcional)
[ ] Armazenar url_s3 no banco
Fase 3 — Backend — Módulos MVP 
3.1 Usuários & Perfil
[ ] GET /users/me — perfil logado
[ ] PATCH /users/me — editar bio, foto, privacidade
[ ] GET /users/{username} — perfil público (respeita is_private)
[ ] GET /users/{id}/posts — posts do usuário
3.2 Sistema de Seguidores
[ ] POST /follows/{user_id} — seguir (se privado → pending)
[ ] PATCH /follows/{user_id} — aceitar/rejeitar (para quem é seguido)
[ ] DELETE /follows/{user_id} — deixar de seguir
[ ] GET /follows/{user_id}/followers e /following
3.3 Feed & Posts
[ ] POST /posts — criar post (legenda + mídia opcional + meal_plan_id opcional)
[ ] GET /feed — timeline: posts de quem sigo + meus posts, ordenado por created_at DESC
[ ] GET /posts/{id} — detalhe do post com likes e comentários
[ ] DELETE /posts/{id} — soft delete
3.4 Likes (múltiplos permitidos)
[ ] POST /posts/{id}/like — cada chamada = 1 like (usuário pode clicar várias vezes)
[ ] GET /posts/{id}/likes — lista de curtidas ordenada por created_at (ranking)
3.5 Comentários
[ ] POST /posts/{id}/comments — criar comentário
[ ] GET /posts/{id}/comments — listar (paginado)
[ ] DELETE /comments/{id} — soft delete
3.6 Dieta — Alimentos
[ ] POST /alimentos — criar alimento (vai para status='pending' se não for admin)
[ ] GET /alimentos — listar só approved (busca por nome com ILIKE ou full-text)
[ ] GET /alimentos/{id} — detalhe
[ ] PATCH /alimentos/{id}/approve — endpoint admin para aprovar
3.7 Dieta — Registro Diário
[ ] POST /alimentacao — registrar refeição do dia
[ ] GET /alimentacao?data=YYYY-MM-DD — diário do dia
[ ] DELETE /alimentacao/{id} — soft delete
[ ] GET /alimentacao/resumo?data=YYYY-MM-DD — retorna os dados da view v_resumo_diario
3.8 Dieta — Meal Plans
[ ] POST /meal-plans — criar plano (só 1 ativo por usuário → tratado no banco)
[ ] POST /meal-plans/{id}/items — adicionar alimentos ao plano
[ ] GET /meal-plans — listar planos do usuário
[ ] GET /meal-plans/{id} — detalhe com itens
[ ] POST /posts com meal_plan_id — publicar plano no feed
Fase 4 — Frontend — Estrutura & UI Base 
4.1 Navegação & Tema
[ ] BottomNavigationBar com 3 abas: Home, Feed, Dieta
[ ] Tema claro/escuro (Material 3)
[ ] Componentes compartilhados: AppButton, AppInput, LoadingWidget, ErrorWidget
4.2 Autenticação (Telas)
[ ] Tela de Login
[ ] Tela de Cadastro
[ ] Tela de Splash / Verificação de token
[ ] Persistência do token: flutter_secure_storage
4.3 State Management
[ ] Provider/Riverpod para estado global: AuthState, UserState
[ ] Repositories pattern: AuthRepository, PostRepository, DietRepository
Fase 5 — Frontend — Telas MVP 
5.1 Aba Home (Perfil & Explorar)
[ ] Header com foto, nome, bio, contadores (posts, seguidores, seguindo)
[ ] Grid de posts do usuário logado (estilo Instagram)
[ ] Botão "Editar Perfil"
[ ] Toggle de privacidade
5.2 Aba Feed (Timeline)
[ ] Lista infinita (scroll) de posts
[ ] Card de post: foto/vídeo, legenda, botão de like (múltiplos toques = múltiplos likes), contador, comentários
[ ] Botão de comentar (bottom sheet)
[ ] Botão de seguir/desseguir no header do post
[ ] Se o post tiver meal_plan_id, mostrar badge "Plano Alimentar" com preview
5.3 Aba Dieta
Sub-abas ou bottom sheet:
[ ] Registro Diário:
Calendário para selecionar data
Lista de refeições do dia (por horário/refeição)
Botão "+" para adicionar alimento (busca no catálogo)
Resumo nutricional do dia (carbo, proteína, calorias)
[ ] Meal Plans:
Lista de planos criados
Criar novo plano (nome, descrição)
Adicionar alimentos ao plano (com quantidade e horário)
Botão "Publicar no Feed" → cria post vinculado ao plano
[ ] Catálogo de Alimentos:
Busca com debounce
Cadastrar novo alimento (vai para moderação)
Fase 6 — Integração & Testes 
6.1 Testes Backend
[ ] Pytest: testes unitários para services
[ ] Testes de integração para rotas críticas (auth, feed, dieta)
[ ] Testar constraints do banco (plano ativo único, alimento duplicado, etc.)
6.2 Testes Frontend
[ ] Widget tests para telas principais
[ ] Testes de integração: login → criar post → curtir → comentar
6.3 Testes Manuais
[ ] Fluxo completo: cadastro → logar → adicionar alimento → registrar refeição → criar plano → publicar no feed → curtir próprio post → seguir outro usuário
[ ] Testar perfil privado: solicitar follow → aceitar → ver posts
[ ] Testar S3: upload de imagem no post
Fase 7 — Deploy 
7.1 Backend
[ ] Opção A (recomendada): Railway, Render ou Fly.io (Python + PostgreSQL fácil)
[ ] Opção B: AWS ECS/Fargate (mais controle, mais complexo)
[ ] Configurar DATABASE_URL apontando para Neon (produção)
[ ] Configurar variáveis de ambiente no serviço
[ ] Rodar alembic upgrade head no startup
[ ] Health check endpoint: GET /health
7.2 Frontend (Flutter)
[ ] Android: Build APK/AAB, publicar na Play Store (Internal Testing primeiro)
[ ] iOS: Build IPA, publicar no TestFlight (requer Apple Developer $99/ano)
[ ] Configurar API_BASE_URL para o domínio do backend deployado
[ ] Configurar S3 bucket de produção
7.3 Neon (Banco)
[ ] Criar projeto Neon (produção)
[ ] Aplicar schema v1.1
[ ] Configurar connection pooling (PgBouncer já vem no Neon)
[ ] Backups automáticos (Neon faz, mas verificar retenção)
7.4 Monitoramento
[ ] Logs: integrar com Sentry ou Logtail
[ ] Métricas básicas: tempo de resposta da API, erros 500
[ ] Alerta se health check falhar   