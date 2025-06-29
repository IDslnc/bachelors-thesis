import random
import re
from flask import Flask, render_template, request, redirect, flash, url_for, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
import plotly
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
import json
import io
import math
import os
import plotly.io as pio
import uuid


app = Flask(__name__)
app.secret_key = '588fh5g7d3'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fproject.db'
db = SQLAlchemy(app)
manager = LoginManager(app)


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)


class Graph(db.Model):
    __tablename__ = 'graph'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    graphjson = db.Column(db.String)
    user = db.relationship('User', backref=db.backref('graphs', lazy='dynamic'))


@manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    login = request.form.get('login')
    password = request.form.get('password')

    if login and password:
        user = User.query.filter_by(login=login).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            session['login'] = login
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect('/')
        else:
            flash('Что-то введено неверно.')
    else:
        flash('Заполните поля логин и пароль.')

    return render_template("login.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    login = request.form.get('login')
    password = request.form.get('password')
    password2 = request.form.get('password2')

    if request.method == 'POST':
        if not (login or password or password2):
            flash('Заполните все поля')
        elif password != password2:
            flash('Пароли не совпадают')
        else:
            hash_pwd = generate_password_hash(password)
            new_user = User(login=login, password=hash_pwd)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login_page'))

    return render_template('register.html')


@app.after_request
def redirect_to_signin(response):
    if response.status_code == 401:
        return redirect(url_for('login_page') + '?next=' + request.url)

    return response


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    session.pop('login', None)
    logout_user()
    return redirect(url_for('index'))


def replace_numpy_functions(formula):
    numpy_functions = [
        'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
        'sqrt', 'log', 'log10', 'exp', 'fabs', 'ceil', 'floor', 'power',
        'fmod', 'modf', 'isnan', 'isinf', 'trunc'
    ]  # Список математических функций из numpy

    pattern = r'(\b({})\b)(?=\()'.format('|'.join(numpy_functions))
    # Используем регулярное выражение, чтобы найти все математические функции

    def replace_function(match):
        return 'np.' + match.group(0)

    replaced_formula = re.sub(pattern, replace_function, formula)
    return replaced_formula


@app.route('/start_plot', methods=['POST'])
def start_plot():
    formula = request.form['formula']
    formula_replaced = replace_numpy_functions(formula)
    x = np.linspace(-10, 10, 100)
    y = eval(formula_replaced)
    fig = go.Figure()
    fig.update_yaxes(range=[-10, 10], zeroline=True, zerolinewidth=3, zerolinecolor='LightPink')
    fig.update_xaxes(range=[-10, 10], zeroline=True, zerolinewidth=3, zerolinecolor='LightGreen')
    fig.add_trace(go.Scatter(x=x, y=y, mode='markers', name=formula,
                             marker=dict(color=y, colorbar=dict(title=formula), colorscale='Inferno',
                                         size=3*abs(x), line=dict(color='Black', width=2)),
                             line=dict(color='Black')))
    fig.update_layout(title=formula, xaxis_title='x', yaxis_title='y', xaxis_autorange=True, yaxis_autorange=True,
                      hovermode='x unified')
    fig.update_traces(hoverinfo="all", hovertemplate="<br>Аргумент: %{x}<br>Функция: %{y}")
    plot_div = fig.to_html(full_html=False)

    return jsonify({'plot_div': plot_div})


@app.route('/')
def index():
    if 'login' in session:
        return render_template("index.html", login=session['login'], islogin=True)
    else:
        return render_template("index.html", islogin=False)


@app.route('/about')
@login_required
def about():
    return render_template("about.html")


@app.route('/create-graphic')
@login_required
def create_graphic():
    return render_template("create-graphic.html")


def generate_random_color():
    color = '#' + ''.join(random.choices('0123456789abcdef', k=6))
    return color


@app.route('/graphic', methods=['POST', 'GET'])
@login_required
def graphic():
    try:
        n = int(request.form['howMuch'])
        formulas = [request.form['formula' + str(i)] for i in range(n)]
        start = float(request.form['start'])
        end = float(request.form['end'])
        step = float(request.form['step'])

        fig = go.Figure()
        fig.update_yaxes(range=[start, 3 * end], zeroline=True, zerolinewidth=3, zerolinecolor='LightPink')
        fig.update_xaxes(range=[start, end], zeroline=True, zerolinewidth=3, zerolinecolor='LightGreen')
        for formula in formulas:
            formula_replaced = replace_numpy_functions(formula)
            x_values = np.arange(start, end + step, step).tolist()
            rounded_x_values = [round(x, 2) for x in x_values]
            if '/' in formula_replaced:
                rounded_x_values.remove(0)

            plus_x = []
            for item in rounded_x_values:
                item = abs(item*3)
                plus_x.append(item)

            y_values = [eval(formula_replaced) for x in rounded_x_values]

            color = generate_random_color()
            fig.add_trace(go.Scatter(x=rounded_x_values, y=y_values, mode='markers', name=formula,
                                     marker=dict(color=color, size=plus_x, line=dict(color='Black', width=2))))
            fig.update_layout(legend_orientation="h", xaxis_autorange=True, yaxis_autorange=True,
                              hovermode="x unified",
                              margin=dict(l=0, r=20, t=40, b=0))
            fig.update_traces(hoverinfo="all", hovertemplate="<br>Аргумент: %{x}<br>Функция: %{y}")

        graph_filename = str(uuid.uuid4()) + '.html'
        graphpath = os.path.join('static', graph_filename)
        graphjson = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        current_user_login = session['login']
        user = User.query.filter_by(login=current_user_login).first()
        graph = Graph(user=user, graphjson=graphjson)
        db.session.add(graph)
        db.session.commit()
        pio.write_html(fig, file=graphpath, auto_open=False)
        return render_template("graphic.html", graphjson=graphjson, graph_filename=graph_filename)
    except:
        return "Ошибка"


@app.route('/download-graphic', methods=['POST', 'GET'])
@login_required
def download_graphic():
    graph_filename = request.args.get('graph_filename')
    graphpath = os.path.join('static', graph_filename)
    return send_file(graphpath, mimetype='text/html', as_attachment=True)


@app.route('/create-visualization', methods=['POST', 'GET'])
@login_required
def create_visual():
    return render_template('create-visualization.html')


def build_bar(df, x, y, color):
    fig = px.bar(df, x=x, y=y, color=color)
    return fig


def build_scatter(df, x, y, size, color):
    fig = px.scatter(df, x=x, y=y, size=size,
                     color=color)
    return fig


def build_box(df, x, y):
    fig = px.box(df, x=x, y=y)
    return fig


def scan_str(firstline):
    if ',' in firstline:
        return ','
    else:
        return ';'


@app.route('/upload_visual', methods=['POST'])
def upload_visual():
    try:
        file = request.files['file']
        filename = file.filename
        file_ext = os.path.splitext(filename)[1]

        if file_ext.lower() in ['.csv', '.xlsx']:
            # Сохраняем загруженный пользователем файл
            file_path = os.path.join('uploads', filename)
            file.save(file_path)

            if file_ext.lower() == '.csv':
                with open(file_path, 'r') as csv_file:
                    first_line = csv_file.readline()
                    delimiter = scan_str(first_line)
                df = pd.read_csv(file_path, delimiter=delimiter)
            else:
                df = pd.read_excel(file_path)

            chart_type = request.form['chart_type']

            if chart_type == 'bar':
                xbar = request.form['xbar']
                ybar = request.form['ybar']
                colorbar = request.form['colorbar']
                fig = build_bar(df, xbar, ybar, colorbar)
            elif chart_type == 'scatter':
                xscatter = request.form['xscatter']
                yscatter = request.form['yscatter']
                sizescatter = request.form['sizescatter']
                colorscatter = request.form['colorscatter']
                fig = build_scatter(df, xscatter, yscatter, sizescatter, colorscatter)
            elif chart_type == 'box':
                xbox = request.form['xbox']
                ybox = request.form['ybox']
                fig = build_box(df, xbox, ybox)
            else:
                return "Неверный тип графика!"

            vis_filename = str(uuid.uuid4()) + '.html'
            vis_path = os.path.join('static', vis_filename)
            visualjson = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

            current_user_login = session['login']
            user = User.query.filter_by(login=current_user_login).first()
            graph = Graph(user=user, graphjson=visualjson)
            db.session.add(graph)
            db.session.commit()
            pio.write_html(fig, file=vis_path, auto_open=False)
            # Удаляем загруженный пользователем файл
            os.remove(file_path)
            return render_template('visualization.html', visualjson=visualjson, vis_filename=vis_filename)
        else:
            return "Неподдерживаемый формат файла!"
    except:
        return "Что-то пошло не так."


@app.route('/download_visual')
def download_visual():
    vis_filename = request.args.get('vis_filename')
    vis_path = os.path.join('static', vis_filename)
    return send_file(vis_path, as_attachment=True)


@app.route('/graph_feed')
@login_required
def graph_feed():
    graphs = Graph.query.order_by(Graph.id.desc()).all()
    return render_template('graph_feed.html', graphs=graphs)


@app.route('/delete_graph', methods=['POST'])
def delete_graph():
    graph_id = request.form.get('graph_id')
    graph = Graph.query.get(graph_id)

    if graph and graph.user.id == current_user.id:
        db.session.delete(graph)
        db.session.commit()

    return redirect(url_for('graph_feed'))


if __name__ == "__main__":
    app.run(debug=True)
