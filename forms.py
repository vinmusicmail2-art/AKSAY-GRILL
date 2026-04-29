"""
WTForms-формы для админки и публичных страниц.
"""
from flask_wtf import FlaskForm
from wtforms import (
    IntegerField,
    PasswordField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.fields import DateField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
)


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


class BusinessLunchOrderForm(FlaskForm):
    """Заявка на корпоративные бизнес-ланчи."""

    contact_name = StringField(
        "Контактное лицо",
        validators=[
            DataRequired(message="Укажите имя контактного лица"),
            Length(min=2, max=128),
        ],
    )
    company = StringField(
        "Компания",
        validators=[Optional(), Length(max=255)],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите телефон для связи"),
            Length(min=5, max=64),
            Regexp(
                r"^[\d\s+()\-]+$",
                message="Только цифры, пробелы и + ( ) -",
            ),
        ],
    )
    email = StringField(
        "E-mail",
        validators=[Optional(), Email(message="Некорректный e-mail"), Length(max=255)],
    )
    persons = IntegerField(
        "Количество человек",
        validators=[
            DataRequired(message="Укажите количество персон"),
            NumberRange(min=1, max=500, message="От 1 до 500"),
        ],
    )
    delivery_date = DateField(
        "Дата доставки",
        validators=[DataRequired(message="Выберите дату доставки")],
    )
    delivery_time = StringField(
        "Время доставки",
        validators=[Optional(), Length(max=16)],
    )
    delivery_address = TextAreaField(
        "Адрес доставки",
        validators=[
            DataRequired(message="Укажите адрес доставки"),
            Length(min=5, max=500),
        ],
    )
    selected_combos = SelectMultipleField(
        "Выбранные комплексы",
        choices=[],  # заполняется в роуте из BUSINESS_LUNCH_MENU
    )
    comment = TextAreaField(
        "Комментарий",
        validators=[Optional(), Length(max=1000)],
    )
    submit = SubmitField("Отправить заявку")
