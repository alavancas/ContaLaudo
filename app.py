from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, flash, g, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from datetime import datetime
from dateutil.relativedelta import relativedelta
from supabase import create_client
from dotenv import load_dotenv
import os
import sys
from procedimentos_data import PROCEDIMENTOS_BASE
from sqlalchemy import case

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

# Configuração do banco de dados usando a URL do Supabase
SUPABASE_DB_URL = os.getenv('SUPABASE_DB_URL')
if SUPABASE_DB_URL and 'postgresql://' in SUPABASE_DB_URL:
    # Adiciona SSL mode=require para conexões em produção
    if '?' in SUPABASE_DB_URL:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"{SUPABASE_DB_URL}&sslmode=require"
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"{SUPABASE_DB_URL}?sslmode=require"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = SUPABASE_DB_URL

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialização dos objetos
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do Supabase
supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Configuração do site URL para o Supabase
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8080')
CALLBACK_URL = f"{SITE_URL}/auth/callback"

@app.before_request
def before_request():
    if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
        # Apenas para PostgreSQL
        if hasattr(g, 'db_conn'):
            try:
                g.db_conn.rollback()
            except:
                pass

@app.teardown_request
def teardown_request(exception=None):
    if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
        # Apenas para PostgreSQL
        if hasattr(g, 'db_conn'):
            try:
                if exception:
                    g.db_conn.rollback()
                else:
                    g.db_conn.commit()
            except:
                pass

@app.teardown_appcontext
def shutdown_session(exception=None):
    if exception:
        db.session.rollback()
    db.session.remove()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nome = db.Column(db.String(80), nullable=False)
    
    periodos = db.relationship('Periodo', backref='user', lazy=True)
    instituicoes = db.relationship('Instituicao', backref='user', lazy=True)

class Instituicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    periodos = db.relationship('Periodo', backref='instituicao', lazy=True)

class Periodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    instituicao_id = db.Column(db.Integer, db.ForeignKey('instituicao.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False)
    tipo_remuneracao = db.Column(db.String(20), nullable=False)
    valor_fixo = db.Column(db.Float, nullable=True)
    laudos = db.relationship('Laudo', backref='periodo', lazy=True)

class Procedimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    tipo_laudo = db.Column(db.String(50), nullable=False)
    especialidade_medica = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=True)
    pontos_rede_dor = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    laudos = db.relationship('Laudo', backref='procedimento', lazy=True)
    
    def __repr__(self):
        return f'<Procedimento {self.nome}>'

class Laudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.id'), nullable=False)
    procedimento_id = db.Column(db.Integer, db.ForeignKey('procedimento.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_cadastro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    comentarios = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Laudo {self.id}>'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except:
        db.session.rollback()
        return None

def importar_procedimentos_base(user_id):
    """Importa a lista base de procedimentos para um novo usuário."""
    try:
        print(f"Importando procedimentos base para o usuário {user_id}")
        for proc in PROCEDIMENTOS_BASE:
            procedimento = Procedimento(
                nome=proc['nome'],
                tipo_laudo=proc['tipo_laudo'],
                especialidade_medica=proc['especialidade_medica'],
                valor=proc.get('valor', None),
                pontos_rede_dor=proc.get('pontos_rede_dor', None),
                user_id=user_id
            )
            db.session.add(procedimento)
        
        db.session.commit()
        print(f"Procedimentos base importados com sucesso para o usuário {user_id}")
        return True
    except Exception as e:
        print(f"Erro ao importar procedimentos base: {str(e)}")
        db.session.rollback()
        return False

@app.route('/')
@login_required
def index():
    try:
        # Data atual e selecionada
        hoje = datetime.now()
        mes_selecionado = request.args.get('mes', type=int, default=hoje.month)
        ano_selecionado = request.args.get('ano', type=int, default=hoje.year)
        
        data_selecionada = datetime(ano_selecionado, mes_selecionado, 1)
        primeiro_dia_mes = data_selecionada.replace(day=1)
        ultimo_dia_mes = (primeiro_dia_mes + relativedelta(months=1, days=-1))
        
        # Buscar todos os períodos do usuário
        todos_periodos = Periodo.query.filter_by(
            user_id=current_user.id
        ).order_by(Periodo.data_criacao.desc()).all()
        
        print(f"Debug - Períodos encontrados: {len(todos_periodos)}")
        
        # Período selecionado (padrão: mais recente)
        periodo_selecionado_id = request.args.get('periodo_id', type=int)
        periodo_selecionado = None
        
        if periodo_selecionado_id:
            periodo_selecionado = Periodo.query.get(periodo_selecionado_id)
        elif todos_periodos:
            periodo_selecionado = todos_periodos[0]
        
        # Estatísticas do período selecionado
        total_laudos = 0
        total_valor = 0  # Total da produção (laudos)
        total_periodos_valor = 0  # Total dos valores fixos dos períodos
        
        # Calcular estatísticas para todos os períodos
        for periodo in todos_periodos:
            # Contar laudos apenas do mês selecionado
            laudos_periodo = [
                laudo for laudo in periodo.laudos
                if primeiro_dia_mes <= laudo.data_cadastro <= ultimo_dia_mes
            ]
            
            total_laudos += len(laudos_periodo)
            total_valor += sum(laudo.valor for laudo in laudos_periodo)
            
            # Adicionar valor fixo do período se aplicável
            if periodo.valor_fixo:
                total_periodos_valor += periodo.valor_fixo
        
        total_periodos = len(todos_periodos)
        print(f"Debug - Total de períodos: {total_periodos}")
        
        # Obter todas as instituições do usuário atual
        instituicoes = Instituicao.query.join(Periodo).filter(
            Periodo.user_id == current_user.id
        ).distinct().all()
        
        print(f"Debug - Instituições encontradas: {[i.nome for i in instituicoes]}")
        
        return render_template('index.html',
                             total_laudos=total_laudos,
                             total_valor=total_valor,
                             total_periodos_valor=total_periodos_valor,
                             total_periodos=total_periodos,
                             todos_periodos=todos_periodos,
                             periodo_selecionado=periodo_selecionado,
                             mes_atual=mes_selecionado,
                             ano_atual=ano_selecionado,
                             instituicoes=instituicoes)
    
    except Exception as e:
        print(f"Erro no dashboard: {str(e)}")
        flash('Erro ao carregar o dashboard. Por favor, tente novamente.', 'error')
        return redirect(url_for('index'))

@app.route('/periodos/<int:id>', methods=['GET', 'POST'])
@login_required
def detalhes_periodo(id):
    periodo = Periodo.query.get_or_404(id)
    
    # Verificar se o período pertence ao usuário atual
    if periodo.user_id != current_user.id:
        abort(403)
    
    # Carregar os procedimentos para cada laudo
    for laudo in periodo.laudos:
        laudo.procedimento_nome = laudo.procedimento.nome if laudo.procedimento else ''
    
    return render_template('detalhes_periodo.html', periodo=periodo)

@app.route('/periodos/<int:id>/post', methods=['POST'])
@login_required
def detalhes_periodo_post(id):
    periodo = Periodo.query.get_or_404(id)
    
    if periodo.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        tipo_laudo = request.form.get('tipo_laudo')
        procedimento_id = request.form.get('procedimento_id')
        valor = request.form.get('valor')
        data = request.form.get('data')
        comentarios = request.form.get('comentarios')
        
        if not tipo_laudo or not procedimento_id or not valor or not data:
            abort(400)
            
        procedimento = Procedimento.query.get_or_404(procedimento_id)
        
        laudo = Laudo(
            data_cadastro=datetime.strptime(data, '%Y-%m-%dT%H:%M'),
            tipo=tipo_laudo,
            valor=float(valor.replace(',', '.')),
            comentarios=comentarios,
            periodo_id=periodo.id,
            procedimento_id=procedimento_id
        )
        
        db.session.add(laudo)
        db.session.commit()
        
        flash('Laudo adicionado com sucesso!', 'success')
        return redirect(url_for('detalhes_periodo', id=id))
    
    return render_template('detalhes_periodo.html', periodo=periodo)

@app.route('/novo_periodo', methods=['GET', 'POST'])
@login_required
def novo_periodo():
    print(f"Debug - Método: {request.method}")
    if request.method == 'POST':
        try:
            print(f"Debug - Form data completo: {request.form}")
            
            # Obter dados do formulário
            instituicao_id = request.form.get('instituicao_id')
            nova_instituicao = request.form.get('nova_instituicao')
            tipo_remuneracao = request.form.get('tipo_remuneracao')
            valor_fixo = request.form.get('valor_fixo')
            
            print(f"Debug - Form data: instituicao_id={instituicao_id}, nova_instituicao={nova_instituicao}, tipo_remuneracao={tipo_remuneracao}, valor_fixo={valor_fixo}")
            
            # Validar tipo de remuneração
            if not tipo_remuneracao:
                flash('Selecione o tipo de remuneração.', 'error')
                return redirect(url_for('novo_periodo'))
            
            # Validar valor fixo quando necessário
            if tipo_remuneracao in ['fixo', 'fixo_producao'] and not valor_fixo:
                flash('O valor fixo é obrigatório para o tipo de remuneração selecionado.', 'error')
                return redirect(url_for('novo_periodo'))
            
            # Criar nova instituição se fornecida
            if nova_instituicao:
                print(f"Debug - Criando nova instituição: {nova_instituicao}")
                
                # Verificar se já existe uma instituição com este nome para o usuário
                instituicao_existente = Instituicao.query.filter_by(
                    nome=nova_instituicao,
                    user_id=current_user.id
                ).first()
                
                if instituicao_existente:
                    flash('Já existe uma instituição com este nome.', 'error')
                    return redirect(url_for('novo_periodo'))
                
                instituicao = Instituicao(
                    nome=nova_instituicao,
                    user_id=current_user.id
                )
                db.session.add(instituicao)
                db.session.flush()  # Obter o ID da nova instituição
                instituicao_id = instituicao.id
                print(f"Debug - Nova instituição criada com ID: {instituicao_id}")
            elif not instituicao_id:
                flash('Selecione uma instituição existente ou crie uma nova.', 'error')
                return redirect(url_for('novo_periodo'))
            else:
                # Verificar se a instituição pertence ao usuário
                instituicao = Instituicao.query.filter_by(
                    id=instituicao_id,
                    user_id=current_user.id
                ).first()
                
                if not instituicao:
                    flash('Instituição inválida.', 'error')
                    return redirect(url_for('novo_periodo'))
            
            # Criar novo período
            periodo = Periodo(
                user_id=current_user.id,
                instituicao_id=int(instituicao_id),
                tipo_remuneracao=tipo_remuneracao,
                valor_fixo=float(valor_fixo) if valor_fixo else None,
                data_criacao=datetime.now()
            )
            
            print(f"Debug - Criando período: user_id={current_user.id}, instituicao_id={instituicao_id}")
            
            db.session.add(periodo)
            db.session.commit()
            
            print(f"Debug - Período criado com ID: {periodo.id}")
            
            flash('Período criado com sucesso!', 'success')
            return redirect(url_for('detalhes_periodo', id=periodo.id))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao criar período: {str(e)}")
            flash('Erro ao criar período. Por favor, tente novamente.', 'error')
            return redirect(url_for('novo_periodo'))
    
    # Mostrar apenas as instituições do usuário
    instituicoes = Instituicao.query.filter_by(user_id=current_user.id).all()
    print(f"Debug - Instituições disponíveis: {[i.nome for i in instituicoes]}")
    
    return render_template('novo_periodo.html', instituicoes=instituicoes)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        nome = request.form.get('nome')
        
        if not email or not nome:
            flash('Por favor, preencha todos os campos.', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado.', 'error')
            return redirect(url_for('register'))
        
        try:
            # Criar novo usuário
            user = User(email=email, nome=nome)
            db.session.add(user)
            db.session.commit()
            
            # Importar procedimentos base
            importar_procedimentos_base(user.id)
            print(f"Procedimentos base importados para o usuário {user.email}")
            
            flash('Cadastro realizado com sucesso! Por favor, faça login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro no cadastro: {str(e)}")
            flash('Erro ao realizar cadastro. Por favor, tente novamente.', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        try:
            # Envia o magic link
            result = supabase.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "email_redirect_to": "http://localhost:8080/verify-magic-link",
                    "redirect_to": "http://localhost:8080/verify-magic-link",
                    "data": {
                        "redirect_url": "http://localhost:8080/verify-magic-link"
                    }
                }
            })
            flash('Link de acesso enviado para seu email!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Erro ao enviar magic link: {str(e)}")  # Para debug
            flash('Erro ao enviar o link. Por favor, tente novamente.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()  # Limpa todas as mensagens da sessão
    logout_user()
    return redirect(url_for('login'))

@app.route('/editar_laudo/<int:laudo_id>', methods=['POST'])
@login_required
def editar_laudo(laudo_id):
    laudo = Laudo.query.get_or_404(laudo_id)
    periodo = Periodo.query.get_or_404(laudo.periodo_id)
    
    # Verificar se o usuário tem permissão para editar este laudo
    if periodo.user_id != current_user.id:
        abort(403)
    
    try:
        tipo_laudo = request.form.get('tipo_laudo')
        valor = request.form.get('valor')
        data = request.form.get('data')
        comentarios = request.form.get('comentarios')
        
        if not tipo_laudo or not valor or not data:
            abort(400)
            
        laudo.tipo = tipo_laudo
        laudo.valor = float(valor.replace(',', '.'))
        laudo.data_cadastro = datetime.strptime(data, '%Y-%m-%dT%H:%M')
        laudo.comentarios = comentarios
        
        db.session.commit()
        return '', 204  # No content, success
    except ValueError:
        db.session.rollback()
        abort(400)
    except Exception as e:
        db.session.rollback()
        abort(500)

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    try:
        mes = request.args.get('mes', type=int)
        ano = request.args.get('ano', type=int)
        instituicoes = request.args.getlist('instituicoes[]')
        
        if not mes or not ano:
            return jsonify({
                'total_laudos': 0,
                'total_valor': 0,
                'total_periodos': 0,
                'total_periodos_valor': 0,
                'periodos': [],
                'graficos': {
                    'periodos_por_instituicao': [],
                    'valor_por_tipo_laudo': []
                }
            })
        
        # Definir o intervalo do mês selecionado
        data_selecionada = datetime(ano, mes, 1)
        primeiro_dia_mes = data_selecionada.replace(day=1)
        ultimo_dia_mes = (primeiro_dia_mes + relativedelta(months=1, days=-1))
        
        print(f"Debug - Buscando períodos para mês {mes}/{ano}")
        
        # Filtrar períodos por instituições selecionadas e data de criação
        query = Periodo.query.filter_by(user_id=current_user.id)
        
        # Filtrar por instituições
        if instituicoes:
            query = query.filter(Periodo.instituicao_id.in_([int(i) for i in instituicoes]))
        
        # Filtrar por data de criação
        query = query.filter(
            Periodo.data_criacao >= primeiro_dia_mes,
            Periodo.data_criacao <= ultimo_dia_mes
        )
        
        periodos = query.order_by(Periodo.data_criacao.desc()).all()
        print(f"Debug - Períodos encontrados: {len(periodos)}")
        
        total_laudos = 0
        total_valor = 0
        total_periodos_valor = 0
        periodos_data = []
        
        # Dados para os gráficos
        periodos_por_instituicao = {}
        valor_por_tipo_laudo = {}
        
        for periodo in periodos:
            # Contagem de períodos por instituição
            inst_nome = periodo.instituicao.nome
            if inst_nome not in periodos_por_instituicao:
                periodos_por_instituicao[inst_nome] = 0
            periodos_por_instituicao[inst_nome] += 1
            
            # Filtrar laudos apenas do mês selecionado
            laudos_periodo = [
                laudo for laudo in periodo.laudos
                if primeiro_dia_mes <= laudo.data_cadastro <= ultimo_dia_mes
            ]
            
            # Soma valores por tipo de laudo
            for laudo in laudos_periodo:
                if laudo.tipo not in valor_por_tipo_laudo:
                    valor_por_tipo_laudo[laudo.tipo] = 0
                valor_por_tipo_laudo[laudo.tipo] += laudo.valor
            
            # Calcular valores do período
            valor_laudos = sum(laudo.valor for laudo in laudos_periodo)
            valor_fixo = periodo.valor_fixo or 0
            
            total_laudos += len(laudos_periodo)
            total_valor += valor_laudos
            total_periodos_valor += valor_fixo
            
            # Adicionar período aos dados
            periodos_data.append({
                'id': periodo.id,
                'instituicao': periodo.instituicao.nome,
                'data_criacao': periodo.data_criacao.strftime('%d/%m/%Y às %H:%M'),
                'total_laudos': len(laudos_periodo),
                'valor_total': valor_laudos,
                'valor_fixo': valor_fixo
            })
        
        print(f"Debug - Total de períodos processados: {len(periodos_data)}")
        
        # Preparar dados dos gráficos
        periodos_grafico = [
            {'label': inst, 'value': count}
            for inst, count in periodos_por_instituicao.items()
        ]
        
        valor_grafico = [
            {'label': tipo, 'value': valor}
            for tipo, valor in valor_por_tipo_laudo.items()
        ]
        
        return jsonify({
            'total_laudos': total_laudos,
            'total_valor': total_valor,
            'total_periodos': len(periodos),
            'total_periodos_valor': total_periodos_valor,
            'periodos': periodos_data,
            'graficos': {
                'periodos_por_instituicao': periodos_grafico,
                'valor_por_tipo_laudo': valor_grafico
            }
        })
        
    except Exception as e:
        print(f"Erro ao gerar dados do dashboard: {str(e)}")
        return jsonify({
            'error': 'Erro ao gerar dados do dashboard'
        }), 500

@app.route('/api/procedimentos')
def list_all_procedimentos():
    try:
        print("=== Iniciando busca de procedimentos ===")
        search = request.args.get('search', '').strip()
        tipo = request.args.get('tipo', '').strip()
        
        print(f"Parâmetros recebidos: search='{search}', tipo='{tipo}'")
        
        query = Procedimento.query
        
        # Se um tipo específico foi selecionado, filtra por ele
        if tipo:
            print(f"Filtrando por tipo: {tipo}")
            query = query.filter(Procedimento.tipo_laudo == tipo)
        
        # Se houver um termo de busca, aplica o filtro de busca
        if search:
            print(f"Filtrando por termo: {search}")
            search_pattern = f"%{search}%"
            query = query.filter(Procedimento.nome.ilike(search_pattern))
        
        # Limita a 50 resultados para não sobrecarregar
        procedimentos = query.limit(50).all()
        
        print(f"Total de procedimentos encontrados: {len(procedimentos)}")
        if procedimentos:
            print("Primeiro procedimento encontrado:")
            print(f"- ID: {procedimentos[0].id}")
            print(f"- Nome: {procedimentos[0].nome}")
            print(f"- Tipo: {procedimentos[0].tipo_laudo}")
        
        return jsonify([{
            'id': p.id,
            'nome': p.nome,
            'tipo_laudo': p.tipo_laudo,
            'valor': float(p.valor) if p.valor else None
        } for p in procedimentos])
        
    except Exception as e:
        print("=== ERRO NA BUSCA DE PROCEDIMENTOS ===")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem: {str(e)}")
        import traceback
        print("Traceback:")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/procedimentos/buscar')
@login_required
def buscar_procedimentos():
    search = request.args.get('search', '').strip()
    tipo = request.args.get('tipo', '').strip()
    
    # Define a ordem dos tipos de laudo
    ordem_tipos = {'RM': 1, 'TC': 2, 'RX': 3, 'USG': 4}
    
    # Inicia a query base
    query = Procedimento.query.filter_by(user_id=current_user.id)
    
    # Aplica os filtros se fornecidos
    if search:
        query = query.filter(Procedimento.nome.ilike(f'%{search}%'))
    if tipo:
        query = query.filter(Procedimento.tipo_laudo == tipo)
    
    # Ordena por tipo (usando a ordem definida) e depois por nome
    procedimentos = query.order_by(
        case([(Procedimento.tipo_laudo == tipo, valor) for tipo, valor in ordem_tipos.items()]),
        Procedimento.nome
    ).all()
    
    return jsonify([{
        'id': p.id,
        'nome': p.nome,
        'tipo_laudo': p.tipo_laudo,
        'valor': float(p.valor) if p.valor else None
    } for p in procedimentos])

@app.route('/importar_procedimentos')
@login_required
def importar_procedimentos():
    # Dados dos procedimentos
    procedimentos_data = [
        # Aqui vou colocar todos os procedimentos da sua lista
        {"nome": "ANGIORM DA AORTA ABDOMINAL", "tipo_laudo": "RM", "especialidade_medica": "MI"},
        {"nome": "ANGIORM DA AORTA TORÁCICA", "tipo_laudo": "RM", "especialidade_medica": "MI"},
        # ... continua com todos os procedimentos
    ]
    
    # Importa os procedimentos
    for proc_data in procedimentos_data:
        proc = Procedimento(
            nome=proc_data['nome'],
            tipo_laudo=proc_data['tipo_laudo'],
            especialidade_medica=proc_data['especialidade_medica'],
            valor=proc_data.get('valor'),
            pontos_rede_dor=proc_data.get('pontos_rede_dor')
        )
        db.session.add(proc)
    
    try:
        db.session.commit()
        flash('Procedimentos importados com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Erro ao importar procedimentos: ' + str(e), 'error')
    
    return redirect(url_for('index'))

@app.route('/verify-magic-link', methods=['GET', 'POST'])
def verify_magic_link():
    if request.method == 'POST':
        try:
            data = request.get_json()
            access_token = data.get('access_token')
            
            if not access_token:
                return jsonify({'success': False, 'message': 'Token não encontrado'}), 400

            # Verificar o token com o Supabase
            user_data = supabase.auth.get_user(access_token)
            
            if user_data and hasattr(user_data, 'user') and user_data.user:
                email = user_data.user.email
                
                # Verificar se o usuário já existe
                user = User.query.filter_by(email=email).first()
                
                if not user:
                    # Criar novo usuário
                    user = User(
                        email=email,
                        nome=email.split('@')[0]  # Usa parte do email como nome inicial
                    )
                    db.session.add(user)
                    db.session.commit()
                    
                    # Importar procedimentos base para o novo usuário
                    importar_procedimentos_base(user.id)
                    print(f"Procedimentos importados para o novo usuário {user.email}", file=sys.stderr)
                
                # Fazer login
                login_user(user)
                return jsonify({'success': True, 'redirect': url_for('index')})
            
            return jsonify({'success': False, 'message': 'Token inválido'}), 401
            
        except Exception as e:
            print(f"Erro ao verificar token: {str(e)}")  # Para debug
            flash('Erro ao verificar o link. Por favor, tente novamente.', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/magic-link', methods=['GET', 'POST'])
def magic_link():
    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            flash('Por favor, informe seu email.', 'error')
            return redirect(url_for('magic_link'))

        try:
            # Enviar magic link com configurações corretas
            res = supabase.auth.sign_in_with_otp({
                "email": email,
                "options": {
                    "email_redirect_to": f"{SITE_URL}/verify-magic-link",
                    "redirect_to": f"{SITE_URL}/verify-magic-link"
                }
            })
            flash('Link de acesso enviado para seu email!', 'success')
            return redirect(url_for('magic_link'))
        except Exception as e:
            print(f"Erro ao enviar magic link: {str(e)}")
            flash('Erro ao enviar link. Por favor, tente novamente.', 'error')
            return redirect(url_for('magic_link'))

    return render_template('login.html')

@app.route('/process-magic-link', methods=['POST'])
def process_magic_link():
    try:
        print("=== DEBUG: Iniciando processamento do magic link ===", file=sys.stderr)
        
        # Pega o hash do formulário
        hash_data = request.form.get('hash', '')
        print(f"Hash recebido: {hash_data}", file=sys.stderr)
        
        if not hash_data:
            print("Erro: Hash não encontrado no formulário", file=sys.stderr)
            flash('Token não encontrado. Por favor, faça login novamente.', 'error')
            return redirect(url_for('login'))

        # Extrai os parâmetros do hash
        params = dict(param.split('=') for param in hash_data.split('&') if '=' in param)
        print(f"Parâmetros extraídos: {params}", file=sys.stderr)
        
        access_token = params.get('access_token')
        refresh_token = params.get('refresh_token')
        print(f"Access Token encontrado: {'Sim' if access_token else 'Não'}", file=sys.stderr)
        print(f"Refresh Token encontrado: {'Sim' if refresh_token else 'Não'}", file=sys.stderr)

        if not access_token:
            print("Erro: Access token não encontrado nos parâmetros", file=sys.stderr)
            flash('Token de acesso não encontrado. Por favor, faça login novamente.', 'error')
            return redirect(url_for('login'))

        try:
            # Configura a sessão do Supabase com o token
            print("Tentando configurar sessão do Supabase...", file=sys.stderr)
            session = supabase.auth.set_session(access_token, refresh_token)
            print("Sessão do Supabase configurada com sucesso", file=sys.stderr)
        except Exception as e:
            print(f"Erro ao configurar sessão do Supabase: {str(e)}", file=sys.stderr)
            raise

        try:
            # Obtém os dados do usuário
            print("Tentando obter dados do usuário...", file=sys.stderr)
            user_response = supabase.auth.get_user()
            user_data = user_response.user
            print(f"Dados do usuário obtidos: {user_data.email if user_data else 'Nenhum'}", file=sys.stderr)
        except Exception as e:
            print(f"Erro ao obter dados do usuário: {str(e)}", file=sys.stderr)
            raise

        if not user_data:
            print("Erro: Dados do usuário não encontrados", file=sys.stderr)
            flash('Usuário não encontrado.', 'error')
            return redirect(url_for('login'))

        try:
            # Verifica se o usuário já existe no banco local
            print(f"Verificando usuário local para email: {user_data.email}", file=sys.stderr)
            local_user = User.query.filter_by(email=user_data.email).first()
            
            if not local_user:
                print("Criando novo usuário local...", file=sys.stderr)
                # Cria um novo usuário local
                local_user = User(
                    email=user_data.email,
                    nome=user_data.email.split('@')[0]  # Usa parte do email como nome temporário
                )
                db.session.add(local_user)
                db.session.commit()
                print(f"Novo usuário local criado: {local_user.email}", file=sys.stderr)
                
                # Importar procedimentos base para o novo usuário
                importar_procedimentos_base(local_user.id)
                print(f"Procedimentos importados para o novo usuário {local_user.email}", file=sys.stderr)
            else:
                print(f"Usuário local encontrado: {local_user.username}", file=sys.stderr)
        except Exception as e:
            print(f"Erro ao gerenciar usuário local: {str(e)}", file=sys.stderr)
            raise

        try:
            # Faz login do usuário
            print("Fazendo login do usuário...", file=sys.stderr)
            login_user(local_user)
            print("Login realizado com sucesso", file=sys.stderr)
        except Exception as e:
            print(f"Erro ao fazer login: {str(e)}", file=sys.stderr)
            raise

        print("=== Processo completado com sucesso ===", file=sys.stderr)
        return redirect(url_for('index'))

    except Exception as e:
        print(f"=== ERRO DETALHADO ===", file=sys.stderr)
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}", file=sys.stderr)
        import traceback
        print("Traceback:")
        print(traceback.format_exc(), file=sys.stderr)
        print("=== FIM DO ERRO ===", file=sys.stderr)
        
        flash('Erro ao verificar o link. Por favor, tente novamente.', 'error')
        return redirect(url_for('login'))

@app.route('/auth/callback')
def auth_callback():
    try:
        # Extrair o hash fragment da URL
        fragment = request.args.get('fragment', '')
        if not fragment and '#' in request.url:
            fragment = request.url.split('#')[1]
        
        # Redirecionar para verify-magic-link com o fragment
        return redirect(f'/verify-magic-link#{fragment}')
    except Exception as e:
        print(f"Erro no callback: {str(e)}")
        flash('Erro no processo de autenticação. Por favor, tente novamente.', 'error')
        return redirect(url_for('magic_link'))

@app.route('/procedimentos')
@login_required
def gerenciar_procedimentos():
    # Define a ordem dos tipos de laudo
    ordem_tipos = {'RM': 1, 'TC': 2, 'RX': 3, 'USG': 4}
    
    # Busca os procedimentos do usuário e ordena primeiro por tipo_laudo (usando a ordem definida) e depois por nome
    procedimentos = Procedimento.query.filter_by(user_id=current_user.id)\
        .order_by(case(
            [(Procedimento.tipo_laudo == tipo, valor) for tipo, valor in ordem_tipos.items()]
        ), Procedimento.nome).all()
    
    return render_template('gerenciar_procedimentos.html', procedimentos=procedimentos)

@app.route('/procedimentos/adicionar', methods=['POST'])
@login_required
def adicionar_procedimento():
    """Adiciona um novo procedimento."""
    try:
        data = request.get_json()
        
        # Validar campos obrigatórios
        if not data.get('nome') or not data.get('tipo_laudo'):
            return jsonify({'success': False, 'error': 'Nome e tipo do laudo são obrigatórios'})
        
        # Criar novo procedimento
        procedimento = Procedimento(
            nome=data['nome'],
            tipo_laudo=data['tipo_laudo'],
            valor=data.get('valor'),
            pontos_rede_dor=data.get('pontos_rede_dor'),
            user_id=current_user.id,
            especialidade_medica='GERAL'  # Valor padrão
        )
        
        db.session.add(procedimento)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/procedimentos/editar/<int:id>', methods=['POST'])
@login_required
def editar_procedimento(id):
    """Edita um procedimento existente."""
    try:
        procedimento = Procedimento.query.get_or_404(id)
        
        # Verificar se o procedimento pertence ao usuário
        if procedimento.user_id != current_user.id:
            abort(403)
        
        data = request.get_json()
        
        # Validar campos obrigatórios
        if not data.get('nome') or not data.get('tipo_laudo'):
            return jsonify({'success': False, 'error': 'Nome e tipo do laudo são obrigatórios'})
        
        # Atualizar dados
        procedimento.nome = data['nome']
        procedimento.tipo_laudo = data['tipo_laudo']
        procedimento.valor = data.get('valor')
        procedimento.pontos_rede_dor = data.get('pontos_rede_dor')
        
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/procedimentos/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_procedimento(id):
    """Exclui um procedimento."""
    try:
        procedimento = Procedimento.query.get_or_404(id)
        
        # Verificar se o procedimento pertence ao usuário
        if procedimento.user_id != current_user.id:
            abort(403)
        
        # Verificar se o procedimento está em uso
        if Laudo.query.filter_by(procedimento_id=id).first():
            return jsonify({'success': False, 'error': 'Não é possível excluir um procedimento que está em uso'})
        
        db.session.delete(procedimento)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/periodos/<int:periodo_id>/laudos/adicionar', methods=['POST'])
@login_required
def adicionar_laudo(periodo_id):
    periodo = Periodo.query.get_or_404(periodo_id)
    
    # Verificar se o período pertence ao usuário atual
    if periodo.user_id != current_user.id:
        abort(403)
    
    try:
        novo_laudo = Laudo(
            periodo_id=periodo_id,
            tipo=request.form.get('tipo'),
            procedimento_id=request.form.get('procedimento_id'),
            valor=float(request.form.get('valor')),
            data_cadastro=datetime.strptime(request.form.get('data_cadastro'), '%Y-%m-%dT%H:%M'),
            comentarios=request.form.get('comentarios')
        )
        
        db.session.add(novo_laudo)
        db.session.commit()
        
        # Buscar o procedimento para incluir o nome na resposta
        procedimento = Procedimento.query.get(novo_laudo.procedimento_id)
        
        return jsonify({
            'success': True,
            'message': 'Laudo adicionado com sucesso!',
            'laudo': {
                'id': novo_laudo.id,
                'tipo': novo_laudo.tipo,
                'valor': float(novo_laudo.valor),
                'data_cadastro': novo_laudo.data_cadastro.strftime('%Y-%m-%dT%H:%M'),
                'comentarios': novo_laudo.comentarios,
                'procedimento_nome': procedimento.nome if procedimento else '',
                'procedimento_id': novo_laudo.procedimento_id,
                'instituicao_nome': periodo.instituicao.nome
            }
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao adicionar laudo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao adicionar laudo'
        }), 500

@app.route('/periodos/<int:periodo_id>/laudos/<int:laudo_id>/editar', methods=['POST'])
@login_required
def editar_laudo_post(periodo_id, laudo_id):
    periodo = Periodo.query.get_or_404(periodo_id)
    laudo = Laudo.query.get_or_404(laudo_id)
    
    # Verificar se o período pertence ao usuário atual
    if periodo.user_id != current_user.id:
        abort(403)
    
    # Verificar se o laudo pertence ao período
    if laudo.periodo_id != periodo_id:
        abort(403)
    
    try:
        laudo.tipo = request.form.get('tipo_laudo')
        laudo.procedimento_id = request.form.get('procedimento_id')
        laudo.valor = float(request.form.get('valor'))
        laudo.data_cadastro = datetime.strptime(request.form.get('data_cadastro'), '%Y-%m-%dT%H:%M')
        laudo.comentarios = request.form.get('comentarios')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Laudo atualizado com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar laudo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao atualizar laudo'
        }), 500

@app.route('/periodos/<int:periodo_id>/laudos/<int:laudo_id>/excluir', methods=['POST'])
@login_required
def excluir_laudo(periodo_id, laudo_id):
    periodo = Periodo.query.get_or_404(periodo_id)
    laudo = Laudo.query.get_or_404(laudo_id)
    
    # Verificar se o período pertence ao usuário atual
    if periodo.user_id != current_user.id:
        abort(403)
    
    # Verificar se o laudo pertence ao período
    if laudo.periodo_id != periodo_id:
        abort(403)
    
    try:
        db.session.delete(laudo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Laudo excluído com sucesso!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao excluir laudo: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro ao excluir laudo'
        }), 500

@app.route('/historico')
@login_required
def historico():
    try:
        # Buscar todos os períodos do usuário ordenados por data de criação
        periodos = Periodo.query.filter_by(
            user_id=current_user.id
        ).order_by(Periodo.data_criacao.desc()).all()
        
        print(f"Debug - Períodos encontrados para user_id={current_user.id}: {len(periodos)}")
        
        # Agrupar períodos por instituição
        periodos_por_instituicao = {}
        for periodo in periodos:
            print(f"Debug - Processando período {periodo.id}: instituicao={periodo.instituicao.nome}, laudos={len(periodo.laudos)}")
            
            if periodo.instituicao.nome not in periodos_por_instituicao:
                periodos_por_instituicao[periodo.instituicao.nome] = []
            periodos_por_instituicao[periodo.instituicao.nome].append({
                'id': periodo.id,
                'data_criacao': periodo.data_criacao,
                'total_laudos': len(periodo.laudos),
                'valor_total': sum(laudo.valor for laudo in periodo.laudos),
                'valor_fixo': periodo.valor_fixo
            })
        
        print(f"Debug - Períodos agrupados: {list(periodos_por_instituicao.keys())}")
        
        return render_template(
            'historico.html',
            periodos_por_instituicao=periodos_por_instituicao
        )
        
    except Exception as e:
        print(f"Erro ao carregar histórico: {str(e)}")
        flash('Erro ao carregar histórico. Por favor, tente novamente.', 'error')
        return redirect(url_for('index'))

@app.route('/debug_db')
@login_required
def debug_db():
    try:
        # Verificar usuário atual
        print(f"\nUsuário atual: id={current_user.id}, email={current_user.email}")
        
        # Verificar todas as instituições
        instituicoes = Instituicao.query.all()
        print("\nInstituições:")
        for i in instituicoes:
            print(f"- ID: {i.id}, Nome: {i.nome}")
        
        # Verificar todos os períodos
        periodos = Periodo.query.all()
        print("\nPeríodos:")
        for p in periodos:
            print(f"- ID: {p.id}, User ID: {p.user_id}, Instituição ID: {p.instituicao_id}, Data: {p.data_criacao}")
            
        # Verificar períodos do usuário atual
        periodos_usuario = Periodo.query.filter_by(user_id=current_user.id).all()
        print(f"\nPeríodos do usuário {current_user.id}:")
        for p in periodos_usuario:
            print(f"- ID: {p.id}, Instituição: {p.instituicao.nome}, Data: {p.data_criacao}")
        
        return jsonify({
            'message': 'Debug info printed to console',
            'user_id': current_user.id,
            'total_instituicoes': len(instituicoes),
            'total_periodos': len(periodos),
            'periodos_usuario': len(periodos_usuario)
        })
    except Exception as e:
        print(f"Erro no debug: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/reset_db')
def reset_db():
    try:
        # Remover todos os laudos
        Laudo.query.delete()
        
        # Remover todos os períodos
        Periodo.query.delete()
        
        # Remover todas as instituições
        Instituicao.query.delete()
        
        # Remover todos os procedimentos
        Procedimento.query.delete()
        
        # Remover todos os usuários
        User.query.delete()
        
        # Commit as mudanças
        db.session.commit()
        
        # Recriar as tabelas
        db.create_all()
        
        return jsonify({'message': 'Database reset successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao resetar DB: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/debug/procedimentos')
def debug_procedimentos():
    try:
        total = Procedimento.query.count()
        amostra = Procedimento.query.limit(5).all()
        
        return jsonify({
            'total': total,
            'amostra': [{
                'id': p.id,
                'nome': p.nome,
                'tipo_laudo': p.tipo_laudo
            } for p in amostra]
        })
    except Exception as e:
        return jsonify({
            'erro': str(e),
            'tipo': type(e).__name__
        }), 500

@app.route('/importar_procedimentos_para_usuario/<email>')
def importar_procedimentos_para_usuario(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
        
    try:
        # Importa os procedimentos base para o usuário
        importar_procedimentos_base(user.id)
        return jsonify({'message': f'Procedimentos importados com sucesso para {email}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/check_procedimentos/<email>')
def check_procedimentos(email):
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
        
    procedimentos = Procedimento.query.filter_by(user_id=user.id).all()
    return jsonify({
        'email': email,
        'quantidade_procedimentos': len(procedimentos),
        'procedimentos': [{'nome': p.nome, 'tipo_laudo': p.tipo_laudo} for p in procedimentos[:5]]  # Mostra os 5 primeiros como exemplo
    })

@app.route('/periodos/<int:periodo_id>/laudos/<int:laudo_id>', methods=['GET'])
@login_required
def get_laudo(periodo_id, laudo_id):
    periodo = Periodo.query.get_or_404(periodo_id)
    laudo = Laudo.query.get_or_404(laudo_id)
    
    # Verificar se o período pertence ao usuário atual
    if periodo.user_id != current_user.id:
        abort(403)
    
    # Verificar se o laudo pertence ao período
    if laudo.periodo_id != periodo_id:
        abort(403)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'id': laudo.id,
            'tipo': laudo.tipo,
            'valor': laudo.valor,
            'data_cadastro': laudo.data_cadastro.strftime('%Y-%m-%dT%H:%M'),
            'comentarios': laudo.comentarios,
            'procedimento_id': laudo.procedimento_id,
            'procedimento_nome': laudo.procedimento.nome
        })
    
    abort(400)

@app.route('/selecionar_instituicao')
@login_required
def selecionar_instituicao():
    instituicoes = Instituicao.query.filter_by(user_id=current_user.id).all()
    return render_template('selecionar_instituicao.html', instituicoes=instituicoes)

@app.route('/api/instituicoes', methods=['POST'])
@login_required
def criar_instituicao():
    data = request.get_json()
    nova_instituicao = Instituicao(
        nome=data['nome'],
        user_id=current_user.id
    )
    db.session.add(nova_instituicao)
    db.session.commit()
    return jsonify({'id': nova_instituicao.id, 'nome': nova_instituicao.nome})

@app.route('/api/instituicoes/<int:id>', methods=['PUT'])
@login_required
def atualizar_instituicao(id):
    instituicao = Instituicao.query.get_or_404(id)
    if instituicao.user_id != current_user.id:
        abort(403)
    data = request.get_json()
    instituicao.nome = data['nome']
    db.session.commit()
    return jsonify({'id': instituicao.id, 'nome': instituicao.nome})

@app.route('/api/instituicoes/<int:id>', methods=['DELETE'])
@login_required
def excluir_instituicao(id):
    instituicao = Instituicao.query.get_or_404(id)
    if instituicao.user_id != current_user.id:
        abort(403)
    db.session.delete(instituicao)
    db.session.commit()
    return '', 204

@app.route('/api/periodos', methods=['POST'])
@login_required
def criar_periodo():
    data = request.get_json()
    novo_periodo = Periodo(
        user_id=current_user.id,
        instituicao_id=data['instituicao_id'],
        tipo_remuneracao=data['tipo_remuneracao'],
        valor_fixo=data.get('valor_fixo'),
        data_criacao=datetime.now()
    )
    db.session.add(novo_periodo)
    db.session.commit()
    return jsonify({'id': novo_periodo.id, 'message': 'Período criado com sucesso!'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=8000)
