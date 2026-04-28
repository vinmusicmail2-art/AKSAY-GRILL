"""
WTForms-формы для админки.
"""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


class LoginForm(FlaskForm):
    username = StringField(
        "Логин",
        validators=[DataRequired(message="Введите логин"), Length(min=3, max=64)],
    )
    password = PasswordField(
        "Пароль",
        validators=[DataRequired(message="Введите пароль"), Length(min=1, max=128)],
    )
    submit = SubmitField("Войти")


class SetupForm(FlaskForm):
    username = StringField(
        "Логин администратора",
        validators=[
            DataRequired(message="Введите логин"),
            Length(min=3, max=64, message="От 3 до 64 символов"),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Только латиница, цифры и _.-",
            ),
        ],
    )
    password = PasswordField(
        "Пароль",
        validators=[
            DataRequired(message="Введите пароль"),
            Length(min=8, max=128, message="Пароль должен быть от 8 символов"),
        ],
    )
    password_confirm = PasswordField(
        "Повторите пароль",
        validators=[
            DataRequired(message="Повторите пароль"),
            EqualTo("password", message="Пароли не совпадают"),
        ],
    )
    submit = SubmitField("Создать администратора")
