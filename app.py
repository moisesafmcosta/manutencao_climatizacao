# Importa as bibliotecas necessárias
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy.sql import func
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

# 1. CONFIGURAÇÃO BÁSICA DA APLICAÇÃO
app = Flask(__name__)
# Chave Secreta (Pode alterar para qualquer coisa)
app.config['SECRET_KEY'] = 'a-minha-chave-secreta-9876'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///manutencao.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning' 
login_manager.login_message = 'Por favor, faça login para aceder a esta página.'

# 2. DEFINIÇÃO DOS MODELOS (A ESTRUTURA DOS DADOS)
class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    def __repr__(self):
        return f'<User {self.username}>'

class Equipamento(db.Model):
    __tablename__ = 'equipamento'
    id = db.Column(db.Integer, primary_key=True)
    marca_modelo = db.Column(db.String(200), nullable=False)
    capacidade_btu = db.Column(db.Integer, nullable=True)
    local_instalado = db.Column(db.String(200), nullable=False)
    proxima_manutencao = db.Column(db.Date, nullable=True)
    servicos = db.relationship(
        'Servico', 
        back_populates='equipamento', 
        lazy='dynamic', 
        order_by='Servico.data_execucao.desc()',
        cascade='all, delete-orphan'
    )
    def __repr__(self):
        return f'<Equipamento {self.id}: {self.marca_modelo}>'

class Servico(db.Model):
    __tablename__ = 'servico'
    id = db.Column(db.Integer, primary_key=True)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamento.id'), nullable=False)
    equipamento = db.relationship('Equipamento', back_populates='servicos')
    data_execucao = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    descricao = db.Column(db.Text, nullable=True)
    tipo_servico = db.Column(db.String(100), nullable=False)
    prestador_servico = db.Column(db.String(200), nullable=True)
    houve_reposicao_pecas = db.Column(db.Boolean, default=False)
    quais_pecas = db.Column(db.Text, nullable=True)
    valor_servico = db.Column(db.Float, default=0.0)
    valor_pecas = db.Column(db.Float, default=0.0)
    valor_total = db.Column(db.Float, default=0.0) 
    def __repr__(self):
        return f'<Servico {self.id} para Equip. {self.equipamento_id}>'

# 3. ROTAS DA APLICAÇÃO (O "CÉREBRO")
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login falhou. Verifique o utilizador e a senha.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Este nome de utilizador já existe. Escolha outro.')
            return redirect(url_for('register'))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(username=username, password_hash=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Conta criada com sucesso! Pode fazer login.')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar conta.')
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout efetuado com sucesso.')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    todos_equipamentos = Equipamento.query.order_by(Equipamento.local_instalado).all()
    return render_template('index.html', equipamentos=todos_equipamentos)

@app.route('/equipamento/add', methods=['POST'])
@login_required
def adicionar_equipamento():
    marca = request.form.get('marca_modelo')
    local = request.form.get('local_instalado')
    btu_str = request.form.get('capacidade_btu')
    capacidade_btu = int(btu_str) if btu_str and btu_str.isdigit() else None
    data_str = request.form.get('proxima_manutencao')
    proxima_manutencao = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
    novo_equipamento = Equipamento(
        marca_modelo=marca, local_instalado=local,
        capacidade_btu=capacidade_btu, proxima_manutencao=proxima_manutencao
    )
    db.session.add(novo_equipamento)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/equipamento/<int:id>')
@login_required
def detalhe_equipamento(id):
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('equipamento_detalhe.html', equipamento=equipamento)

@app.route('/servico/add', methods=['POST'])
@login_required
def adicionar_servico():
    equip_id = request.form.get('equipamento_id')
    data_exec = datetime.strptime(request.form.get('data_execucao'), '%Y-%m-%d').date()
    tipo = request.form.get('tipo_servico')
    prestador = request.form.get('prestador_servico')
    descricao = request.form.get('descricao')
    houve_reposicao = 'houve_reposicao_pecas' in request.form
    quais_pecas = request.form.get('quais_pecas')
    val_servico = float(request.form.get('valor_servico') or 0)
    val_pecas = float(request.form.get('valor_pecas') or 0)
    val_total = val_servico + val_pecas
    novo_servico = Servico(
        equipamento_id=equip_id, data_execucao=data_exec, tipo_servico=tipo,
        prestador_servico=prestador, descricao=descricao, 
        houve_reposicao_pecas=houve_reposicao, quais_pecas=quais_pecas,
        valor_servico=val_servico, valor_pecas=val_pecas, valor_total=val_total
    )
    db.session.add(novo_servico)
    db.session.commit()
    return redirect(url_for('detalhe_equipamento', id=equip_id))

@app.route('/relatorios')
@login_required
def relatorios():
    total_gasto = db.session.query(func.sum(Servico.valor_total)).scalar() or 0.0
    total_pecas = db.session.query(func.sum(Servico.valor_pecas)).scalar() or 0.0
    total_servicos_val = db.session.query(func.sum(Servico.valor_servico)).scalar() or 0.0
    count_total = Servico.query.count()
    count_preventivas = Servico.query.filter_by(tipo_servico='Preventivo').count()
    count_corretivas = Servico.query.filter_by(tipo_servico='Corretivo').count()
    totais = {
        "gasto_total": total_gasto, "gasto_pecas": total_pecas,
        "gasto_servicos": total_servicos_val, "count_total": count_total,
        "count_preventivas": count_preventivas, "count_corretivas": count_corretivas
    }
    relatorio_equipamentos = db.session.query(
        Equipamento, func.count(Servico.id).label('contagem_servicos')
    ).outerjoin(Servico, Servico.equipamento_id == Equipamento.id)\
     .group_by(Equipamento.id).order_by(Equipamento.local_instalado).all()
    servicos_com_pecas = Servico.query.filter(Servico.houve_reposicao_pecas == True)\
                                     .order_by(Servico.data_execucao.desc()).all()
    return render_template(
        'relatorios.html', totais=totais,
        relatorio_equipamentos=relatorio_equipamentos,
        servicos_com_pecas=servicos_com_pecas
    )

@app.route('/equipamento/edit/<int:id>')
@login_required
def editar_equipamento(id):
    equipamento = Equipamento.query.get_or_404(id)
    return render_template('equipamento_edit.html', equipamento=equipamento)

@app.route('/equipamento/update/<int:id>', methods=['POST'])
@login_required
def atualizar_equipamento(id):
    equipamento_para_atualizar = Equipamento.query.get_or_404(id)
    equipamento_para_atualizar.marca_modelo = request.form.get('marca_modelo')
    equipamento_para_atualizar.local_instalado = request.form.get('local_instalado')
    btu_str = request.form.get('capacidade_btu')
    equipamento_para_atualizar.capacidade_btu = int(btu_str) if btu_str and btu_str.isdigit() else None
    data_str = request.form.get('proxima_manutencao')
    equipamento_para_atualizar.proxima_manutencao = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else None
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/equipamento/delete/<int:id>', methods=['POST'])
@login_required
def apagar_equipamento(id):
    equipamento_para_apagar = Equipamento.query.get_or_404(id)
    db.session.delete(equipamento_para_apagar)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/servico/edit/<int:id>')
@login_required
def editar_servico(id):
    servico = Servico.query.get_or_404(id)
    return render_template('servico_edit.html', servico=servico)

@app.route('/servico/update/<int:id>', methods=['POST'])
@login_required
def atualizar_servico(id):
    servico_para_atualizar = Servico.query.get_or_404(id)
    data_exec = datetime.strptime(request.form.get('data_execucao'), '%Y-%m-%d').date()
    tipo = request.form.get('tipo_servico')
    prestador = request.form.get('prestador_servico')
    descricao = request.form.get('descricao')
    houve_reposicao = 'houve_reposicao_pecas' in request.form
    quais_pecas = request.form.get('quais_pecas')
    val_servico = float(request.form.get('valor_servico') or 0)
    val_pecas = float(request.form.get('valor_pecas') or 0)
    val_total = val_servico + val_pecas
    servico_para_atualizar.data_execucao = data_exec
    servico_para_atualizar.tipo_servico = tipo
    servico_para_atualizar.prestador_servico = prestador
    servico_para_atualizar.descricao = descricao
    servico_para_atualizar.houve_reposicao_pecas = houve_reposicao
    servico_para_atualizar.quais_pecas = quais_pecas
    servico_para_atualizar.valor_servico = val_servico
    servico_para_atualizar.valor_pecas = val_pecas
    servico_para_atualizar.valor_total = val_total
    db.session.commit()
    return redirect(url_for('detalhe_equipamento', id=servico_para_atualizar.equipamento_id))

@app.route('/servico/delete/<int:id>', methods=['POST'])
@login_required
def apagar_servico(id):
    servico_para_apagar = Servico.query.get_or_404(id)
    equip_id = request.form.get('equipamento_id')
    db.session.delete(servico_para_apagar)
    db.session.commit()
    return redirect(url_for('detalhe_equipamento', id=equip_id))

# 4. EXECUTAR A APLICAÇÃO
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
