-- ============================================================
-- Fitness Hub - Database Schema
-- Neon (PostgreSQL Serverless) - MVP v1.1 (Corrigido)
-- ============================================================
-- Correções v1.1:
-- 1. Tabelas de alimentação reordenadas ANTES de post_media (forward reference)
-- 2. CHECK (porcao_base_g > 0) em alimentos — evita division by zero
-- 3. Índice único parcial: 1 plano ativo por usuário
-- 4. Índice único parcial: alimentos duplicados por usuário
-- 5. Trigger defense-in-depth: só alimentos "approved" em alimentacao/meal_plan_items
-- 6. Renomeado alimentos.gramas -> porcao_base_g (semântica clara)
-- 7. Soft delete (deleted_at) em alimentacao
-- ============================================================

-- --------------------------------------------------------
-- 1. TABELA: Usuarios
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    senha_hash VARCHAR(255) NOT NULL,
    nome_completo VARCHAR(100),
    genero VARCHAR(20),
    nascimento DATE,
    is_private BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    bio TEXT,
    foto_url_s3 TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE usuarios IS 'Usuários da plataforma fitness-social';
COMMENT ON COLUMN usuarios.senha_hash IS 'Sempre armazenar hash (bcrypt/argon2), nunca texto plano';
COMMENT ON COLUMN usuarios.is_private IS 'Se TRUE, seguidores precisam de aprovação (status=pending)';

-- --------------------------------------------------------
-- 2. TABELA: Alimentos (tabela base/catalogo)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS alimentos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    carbo FLOAT DEFAULT 0,
    protein FLOAT DEFAULT 0,
    porcao_base_g FLOAT NOT NULL DEFAULT 100 CHECK (porcao_base_g > 0),
    calorias FLOAT DEFAULT 0,
    acucares FLOAT DEFAULT 0,
    fibras FLOAT DEFAULT 0,
    sodio FLOAT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejeitado_motivo TEXT,
    created_by INT REFERENCES usuarios(id) ON DELETE SET NULL,
    reviewed_by INT REFERENCES usuarios(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE alimentos IS 'Catálogo base de alimentos com informações nutricionais por porção';
COMMENT ON COLUMN alimentos.porcao_base_g IS 'Quantidade de gramas à qual os macros se referem (ex: 100g, 30g por scoop, 15g por unidade)';
COMMENT ON COLUMN alimentos.status IS 'pending = aguardando moderação; approved = liberado; rejected = rejeitado';
COMMENT ON COLUMN alimentos.rejeitado_motivo IS 'Motivo da rejeição, preenchido apenas quando status = rejected';

-- --------------------------------------------------------
-- 3. TABELA: meal_plans (planos alimentares - cabeçalho)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS meal_plans (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE meal_plans IS 'Planos alimentares criados pelo usuário (ex: Cutting, Bulking, Dieta da Semana)';
COMMENT ON COLUMN meal_plans.is_public IS 'Se TRUE, outros usuários podem ver e copiar este plano';

-- --------------------------------------------------------
-- 4. TABELA: meal_plan_items (itens de cada plano)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS meal_plan_items (
    id SERIAL PRIMARY KEY,
    meal_plan_id INT NOT NULL REFERENCES meal_plans(id) ON DELETE CASCADE,
    alimento_id INT NOT NULL REFERENCES alimentos(id) ON DELETE RESTRICT,
    quantidade FLOAT NOT NULL CHECK (quantidade > 0),
    refeicao VARCHAR(30) NOT NULL CHECK (refeicao IN ('cafe_manha', 'lanche_manha', 'almoco', 'lanche_tarde', 'jantar', 'ceia')),
    horario TIME,
    ordem INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE meal_plan_items IS 'Alimentos que compõem cada plano alimentar';
COMMENT ON COLUMN meal_plan_items.quantidade IS 'Quantidade em gramas do alimento neste plano';
COMMENT ON COLUMN meal_plan_items.horario IS 'Horário sugerido para consumo';
COMMENT ON COLUMN meal_plan_items.ordem IS 'Ordem de exibição dentro da mesma refeição';

-- --------------------------------------------------------
-- 5. TABELA: Alimentacao (registro diário do usuário)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS alimentacao (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    data DATE NOT NULL,
    quantidade FLOAT NOT NULL CHECK (quantidade > 0),
    alimento_id INT NOT NULL REFERENCES alimentos(id) ON DELETE RESTRICT,
    refeicao VARCHAR(30) NOT NULL CHECK (refeicao IN ('cafe_manha', 'lanche_manha', 'almoco', 'lanche_tarde', 'jantar', 'ceia')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

COMMENT ON TABLE alimentacao IS 'Diário alimentar do usuário: o que ele realmente comeu em cada dia';
COMMENT ON COLUMN alimentacao.quantidade IS 'Quantidade em gramas consumida naquele registro';
COMMENT ON COLUMN alimentacao.refeicao IS 'Momento do dia em que o alimento foi consumido';

-- --------------------------------------------------------
-- 6. TABELA: PostMedia (Feed / Posts)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS post_media (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    url_s3 TEXT NOT NULL,
    legenda TEXT,
    tipo VARCHAR(20) DEFAULT 'post' CHECK (tipo IN ('post', 'story', 'reel')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_private BOOLEAN DEFAULT FALSE,
    meal_plan_id INT REFERENCES meal_plans(id) ON DELETE SET NULL,
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

COMMENT ON TABLE post_media IS 'Posts do feed (fotos, vídeos, publicações de dieta)';
COMMENT ON COLUMN post_media.meal_plan_id IS 'FK opcional: quando o post é uma publicação de dieta/plano alimentar';
COMMENT ON COLUMN post_media.deleted_at IS 'Soft delete: NULL = ativo, preenchido = deletado';

-- --------------------------------------------------------
-- 7. TABELA: Follows (Seguidores)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS follows (
    id SERIAL PRIMARY KEY,
    follower_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    followed_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'accepted' CHECK (status IN ('pending', 'accepted', 'blocked')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(follower_id, followed_id)
);

COMMENT ON TABLE follows IS 'Relacionamento de seguidores. Status pending quando perfil é privado';
COMMENT ON COLUMN follows.status IS 'pending = aguardando aprovação do followed; accepted = seguindo; blocked = bloqueado';

-- --------------------------------------------------------
-- 8. TABELA: Likes (Curtidas - múltiplas permitidas)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS likes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    post_media_id INT NOT NULL REFERENCES post_media(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE likes IS 'Curtidas em posts. Múltiplas curtidas do mesmo usuário são permitidas (ranking por quantidade)';

-- --------------------------------------------------------
-- 9. TABELA: Comentarios
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS comentarios (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    post_media_id INT NOT NULL REFERENCES post_media(id) ON DELETE CASCADE,
    conteudo TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL
);

COMMENT ON TABLE comentarios IS 'Comentários nos posts do feed';

-- ============================================================
-- ÍNDICES ESTRATÉGICOS (Neon/PostgreSQL performance)
-- ============================================================

-- Usuarios
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- PostMedia (feed, posts de dieta)
CREATE INDEX IF NOT EXISTS idx_postmedia_usuario_created ON post_media(usuario_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_postmedia_meal_plan ON post_media(meal_plan_id) WHERE meal_plan_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_postmedia_deleted_at ON post_media(deleted_at) WHERE deleted_at IS NULL;

-- Follows
CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id, status);
CREATE INDEX IF NOT EXISTS idx_follows_followed ON follows(followed_id, status);

-- Likes (contagem rápida e ranking)
CREATE INDEX IF NOT EXISTS idx_likes_post ON likes(post_media_id);
CREATE INDEX IF NOT EXISTS idx_likes_user_post ON likes(usuario_id, post_media_id);
CREATE INDEX IF NOT EXISTS idx_likes_created ON likes(post_media_id, created_at DESC);

-- Comentarios
CREATE INDEX IF NOT EXISTS idx_comentarios_post ON comentarios(post_media_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comentarios_deleted ON comentarios(deleted_at) WHERE deleted_at IS NULL;

-- Alimentação / Dieta
CREATE INDEX IF NOT EXISTS idx_alimentacao_user_date ON alimentacao(usuario_id, data DESC);
CREATE INDEX IF NOT EXISTS idx_alimentacao_user_refeicao ON alimentacao(usuario_id, data, refeicao);
CREATE INDEX IF NOT EXISTS idx_alimentacao_deleted ON alimentacao(deleted_at) WHERE deleted_at IS NULL;

-- Meal Plans
CREATE INDEX IF NOT EXISTS idx_meal_plans_usuario ON meal_plans(usuario_id, is_active);
CREATE INDEX IF NOT EXISTS idx_meal_plan_items_plan ON meal_plan_items(meal_plan_id, refeicao, ordem);

-- Alimentos (busca e moderação)
CREATE INDEX IF NOT EXISTS idx_alimentos_status ON alimentos(status);
CREATE INDEX IF NOT EXISTS idx_alimentos_nome ON alimentos USING gin(to_tsvector('portuguese', nome));

-- ============================================================
-- ÍNDICES ÚNICOS PARCIAIS (regras de negócio)
-- ============================================================

-- Apenas 1 plano ativo por usuário
CREATE UNIQUE INDEX IF NOT EXISTS idx_meal_plans_active_per_user 
ON meal_plans(usuario_id) WHERE is_active = TRUE;

-- Evita alimentos duplicados por usuário (case-insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS idx_alimentos_unique_per_user
ON alimentos(LOWER(nome), created_by) 
WHERE created_by IS NOT NULL;

-- ============================================================
-- TRIGGER: updated_at automático em todas as tabelas
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_usuarios_updated_at BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_post_media_updated_at BEFORE UPDATE ON post_media
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_follows_updated_at BEFORE UPDATE ON follows
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_comentarios_updated_at BEFORE UPDATE ON comentarios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_alimentos_updated_at BEFORE UPDATE ON alimentos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_alimentacao_updated_at BEFORE UPDATE ON alimentacao
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_meal_plans_updated_at BEFORE UPDATE ON meal_plans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_meal_plan_items_updated_at BEFORE UPDATE ON meal_plan_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- TRIGGER: Defense in depth — só alimentos "approved" em logs/planos
-- ============================================================
CREATE OR REPLACE FUNCTION check_alimento_approved()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT status FROM alimentos WHERE id = NEW.alimento_id) != 'approved' THEN
        RAISE EXCEPTION 'Alimento não aprovado (status != approved). ID: %', NEW.alimento_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_alimentacao_approved BEFORE INSERT OR UPDATE ON alimentacao
    FOR EACH ROW EXECUTE FUNCTION check_alimento_approved();

CREATE TRIGGER trigger_meal_plan_items_approved BEFORE INSERT OR UPDATE ON meal_plan_items
    FOR EACH ROW EXECUTE FUNCTION check_alimento_approved();

-- ============================================================
-- VIEWS ÚTEIS
-- ============================================================

-- View: Resumo nutricional diário do usuário
CREATE OR REPLACE VIEW v_resumo_diario AS
SELECT 
    a.usuario_id,
    a.data,
    a.refeicao,
    SUM(a.quantidade) as total_gramas,
    SUM((al.carbo / al.porcao_base_g) * a.quantidade) as total_carbo,
    SUM((al.protein / al.porcao_base_g) * a.quantidade) as total_protein,
    SUM((al.calorias / al.porcao_base_g) * a.quantidade) as total_calorias,
    SUM((al.fibras / al.porcao_base_g) * a.quantidade) as total_fibras
FROM alimentacao a
JOIN alimentos al ON al.id = a.alimento_id
WHERE a.deleted_at IS NULL
GROUP BY a.usuario_id, a.data, a.refeicao;

COMMENT ON VIEW v_resumo_diario IS 'Resumo nutricional por refeição e dia para o usuário';

-- View: Contagem de likes por post (para ranking)
CREATE OR REPLACE VIEW v_post_likes_count AS
SELECT 
    post_media_id,
    COUNT(*) as total_likes,
    COUNT(DISTINCT usuario_id) as usuarios_unicos
FROM likes
GROUP BY post_media_id;

COMMENT ON VIEW v_post_likes_count IS 'Total de curtidas e usuários únicos por post';

-- ============================================================
-- FIM DO SCHEMA
-- ============================================================
