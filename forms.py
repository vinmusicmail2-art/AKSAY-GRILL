"""
WTForms-формы для админки и публичных страниц.
"""
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
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
                r"^[A-Za-z0-9А-Яа-яЁё_.-]+$",
                message="Только буквы, цифры и _.-",
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


class CateringRequestForm(FlaskForm):
    """Заявка на кейтеринговое обслуживание мероприятия."""

    contact_name = StringField(
        "Контактное лицо",
        validators=[
            DataRequired(message="Укажите имя контактного лица"),
            Length(min=2, max=128),
        ],
    )
    company = StringField(
        "Компания / организатор",
        validators=[Optional(), Length(max=255)],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите телефон для связи"),
            Length(min=5, max=64),
            Regexp(r"^[\d\s+()\-]+$", message="Только цифры, пробелы и + ( ) -"),
        ],
    )
    email = StringField(
        "E-mail",
        validators=[Optional(), Email(message="Некорректный e-mail"), Length(max=255)],
    )
    event_format = SelectField(
        "Формат мероприятия",
        choices=[],  # заполняется в роуте из CATERING_FORMATS
        validators=[DataRequired(message="Выберите формат")],
    )
    guests = IntegerField(
        "Количество гостей",
        validators=[
            DataRequired(message="Укажите число гостей"),
            NumberRange(min=1, max=2000, message="От 1 до 2000"),
        ],
    )
    event_date = DateField(
        "Дата мероприятия",
        validators=[DataRequired(message="Выберите дату мероприятия")],
    )
    event_time = StringField(
        "Время начала",
        validators=[Optional(), Length(max=16)],
    )
    venue = TextAreaField(
        "Площадка / адрес",
        validators=[
            DataRequired(message="Укажите адрес площадки"),
            Length(min=3, max=500),
        ],
    )
    budget_per_guest = IntegerField(
        "Бюджет на гостя, ₽ (если есть)",
        validators=[Optional(), NumberRange(min=0, max=100000)],
    )
    comment = TextAreaField(
        "Комментарий",
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField("Отправить заявку")


class HallReservationForm(FlaskForm):
    """Заявка на бронирование зала ресторана для мероприятия."""

    contact_name = StringField(
        "Контактное лицо",
        validators=[
            DataRequired(message="Укажите имя контактного лица"),
            Length(min=2, max=128),
        ],
    )
    company = StringField(
        "Компания (если корпоративное)",
        validators=[Optional(), Length(max=255)],
    )
    phone = StringField(
        "Телефон",
        validators=[
            DataRequired(message="Укажите телефон для связи"),
            Length(min=5, max=64),
            Regexp(r"^[\d\s+()\-]+$", message="Только цифры, пробелы и + ( ) -"),
        ],
    )
    email = StringField(
        "E-mail",
        validators=[Optional(), Email(message="Некорректный e-mail"), Length(max=255)],
    )
    event_type = SelectField(
        "Тип мероприятия",
        choices=[],  # заполняется в роуте из EVENT_TYPES
        validators=[DataRequired(message="Выберите тип мероприятия")],
    )
    guests = IntegerField(
        "Количество гостей",
        validators=[
            DataRequired(message="Укажите число гостей"),
            NumberRange(min=2, max=300, message="От 2 до 300 гостей"),
        ],
    )
    event_date = DateField(
        "Дата мероприятия",
        validators=[DataRequired(message="Выберите дату мероприятия")],
    )
    event_time = StringField(
        "Время начала",
        validators=[
            DataRequired(message="Укажите время начала"),
            Length(max=16),
        ],
    )
    duration_hours = IntegerField(
        "Длительность, часов",
        validators=[Optional(), NumberRange(min=1, max=12)],
    )
    needs_decor = BooleanField("Нужно оформление зала (шары, цветы, баннер)")
    needs_menu_help = BooleanField("Нужна помощь с подбором меню")
    comment = TextAreaField(
        "Комментарий / пожелания",
        validators=[Optional(), Length(max=2000)],
    )
    submit = SubmitField("Забронировать зал")
