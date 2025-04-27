from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib import messages
from django.db.models import Count, Sum, Q, Min, Avg, F, ExpressionWrapper, FloatField, Max
from django.db.models.functions import Coalesce
from .models import Product, Category, ProductVariant, Order, OrderItem, PaymentMethod, UserProfile, Review
from .forms import UserProfileForm, OrderForm, SignUpForm, ReviewForm, UserNameForm
import random
import requests
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from urllib.parse import urlencode
from yookassa import Configuration, Payment
import uuid
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import LoginView
from .forms import LoginForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin
from .admin import admin_site
from django.apps import apps
from django.urls import reverse
from django.http import HttpResponseRedirect
from .templatetags.custom_filters import get_variant
import re

def home(request):
    # Выбираем топ 50 товаров по количеству звезд и заказов
    popular_products = Product.objects.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        order_count=Count('variants__orderitems'),
        popularity_score=ExpressionWrapper(
            F('avg_rating') * F('order_count'),
            output_field=FloatField()
        )
    ).order_by('-popularity_score')[:50]
    
    return render(request, 'nut_shop/home.html', {'products': popular_products})

def product_list(request):
    categories = Category.objects.all()
    query = request.GET.get('query')
    sort_by = request.GET.get('sort_by', 'name')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    min_rating = request.GET.get('min_rating')
    min_weight = request.GET.get('min_weight')
    max_weight = request.GET.get('max_weight')
    category_id = request.GET.get('category')
    current_category = None

    # Инициализируем products здесь
    products = Product.objects.all()

    if category_id:
        current_category = get_object_or_404(Category, id=category_id)
        products = products.filter(category=current_category)
    
    if query:
        # Проверяем, есть ли в запросе тег id
        id_match = re.match(r'id\((\d+)\)', query)
        if id_match:
            # Если есть, ищем продукт только по ID
            product_id = id_match.group(1)
            products = products.filter(id=product_id)
        else:
            # Если нет, используем обычный поиск
            products = products.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(category__name__icontains=query) |
                Q(variants__weight__icontains=query) |
                Q(variants__price__icontains=query)
            ).distinct()
    
    # Аннотации для сортировки и фильтрации
    products = products.annotate(
        min_price=Min('variants__price'),
        avg_rating=Avg('reviews__rating'),
        order_count=Count('variants__orderitems')
    )
    
    if min_price:
        products = products.filter(min_price__gte=min_price)
    if max_price:
        products = products.filter(min_price__lte=max_price)
    if min_rating:
        products = products.filter(avg_rating__gte=min_rating)
    if min_weight:
        products = products.filter(variants__weight__gte=min_weight)
    if max_weight:
        products = products.filter(variants__weight__lte=max_weight)
    
    # Сортировка
    if sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'price_asc':
        products = products.order_by('min_price')
    elif sort_by == 'price_desc':
        products = products.order_by('-min_price')
    elif sort_by == 'popularity':
        products = products.order_by('-order_count', '-avg_rating')
    
    # Пагинация
    page = request.GET.get('page', 1)
    paginator = Paginator(products, 12)  # 12 продуктов на страницу
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    # Получаем минимальные и максимальные значения цены и веса
    price_range = Product.objects.aggregate(min_price=Min('variants__price'), max_price=Max('variants__price'))
    weight_range = ProductVariant.objects.aggregate(min_weight=Min('weight'), max_weight=Max('weight'))

    min_price = request.GET.get('min_price', price_range['min_price'])
    max_price = request.GET.get('max_price', price_range['max_price'])
    min_weight = request.GET.get('min_weight', weight_range['min_weight'])
    max_weight = request.GET.get('max_weight', weight_range['max_weight'])

    context = {
        'products': products,
        'categories': categories,
        'query': query,
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
        'min_rating': min_rating,
        'min_weight': min_weight,
        'max_weight': max_weight,
        'price_range': price_range,
        'weight_range': weight_range,
        'category_id': category_id,
        'current_category': current_category,  # Добавляем текущую категорию в контекст
    }
    return render(request, 'nut_shop/product_list.html', context)

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.all().order_by('-created_at')
    user_can_review = False
    user_orders = []

    if request.user.is_authenticated:
        user_orders = Order.objects.filter(
            user=request.user, 
            status='delivered', 
            is_completed=True,
            items__product_variant__product=product
        ).distinct()
        user_can_review = user_orders.exists() and not Review.objects.filter(user=request.user, product=product).exists()

    # Получаем рекомендованные товары (максимум 15)
    recommended_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:15]

    if request.method == 'POST' and user_can_review:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            messages.success(request, 'Ваш отзыв успешно добавлен.')
            return redirect('product_detail', pk=pk)
    else:
        form = ReviewForm()

    context = {
        'product': product,
        'reviews': reviews,
        'form': form,
        'user_can_review': user_can_review,
        'user_orders': user_orders,
        'recommended_products': recommended_products,
    }
    return render(request, 'nut_shop/product_detail.html', context)

@login_required
def add_to_cart(request):
    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))  # Получаем количество из формы
        variant = get_object_or_404(ProductVariant, id=variant_id)
        cart = request.session.get('cart', {})
        cart[variant_id] = cart.get(variant_id, 0) + quantity  # Добавляем выбранное количество
        request.session['cart'] = cart
        messages.success(request, f"{variant.product.name} ({variant.weight}г) - {quantity} шт. добавлено в корзину.")
    return redirect('product_list')

@login_required
def cart(request):
    cart = request.session.get('cart', {})
    
    if request.method == 'POST':
        variant_id = request.POST.get('remove_variant')
        if variant_id:
            del cart[variant_id]
            request.session['cart'] = cart
            messages.success(request, "Товар удален из корзины.")
            return redirect('cart')
    
    items = []
    total = 0
    for variant_id, quantity in cart.items():
        variant = get_object_or_404(ProductVariant, id=variant_id)
        item_total = variant.price * quantity
        items.append({
            'variant': variant,
            'quantity': quantity,
            'item_total': item_total
        })
        total += item_total
    return render(request, 'nut_shop/cart.html', {'items': items, 'total': total})

@login_required
def checkout(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            cart = request.session.get('cart', {})
            total_price = Decimal('0')
            
            for variant_id, quantity in cart.items():
                variant = get_variant(variant_id)
                total_price += variant.price * Decimal(quantity)
            
            order.total_price = total_price
            order.status = 'pending_payment'
            order.is_completed = False
            order.save()

            for variant_id, quantity in cart.items():
                variant = get_variant(variant_id)
                OrderItem.objects.create(
                    order=order,
                    product_variant=variant,
                    quantity=quantity,
                    price=variant.price
                )
            
            payment_method = order.payment_method
            if payment_method.name == "По реквизитам":
                return redirect('payment_by_requisites', order_id=order.id)
            elif payment_method.name == "ЮKassa":
                payment_url = create_payment(order, payment_method)
                if payment_url:
                    return redirect(payment_url)
                else:
                    messages.error(request, "Ошибка при создан��и платежа. Пожалуйста, попробуйте позже.")
                    return redirect('cart')
            
            request.session['cart'] = {}
            messages.success(request, "Заказ успешно оформлен.")
            return redirect('order_confirmation', order_id=order.id)
    else:
        form = OrderForm()
    
    cart = request.session.get('cart', {})
    total_price = sum(get_variant(variant_id).price * Decimal(quantity) 
                      for variant_id, quantity in cart.items())
    
    return render(request, 'nut_shop/checkout.html', {'form': form, 'total_price': total_price})

def create_yoomoney_payment(order, payment_method):
    api_url = "https://yoomoney.ru/api/request-payment"
    payload = {
        "amount": str(order.total_price),
        "currency": "RUB",
        "comment": f"Оплата заказа №{order.id}  Орех Маркет",
        "return_url": f"{settings.SITE_DOMAIN}/payment-success/{order.id}/",
        "quickpay_form": "shop",
        "receiver": payment_method.yoomoney_wallet,
        "label": str(order.id),
        "token": payment_method.yoomoney_secret_key
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Bearer {payment_method.yoomoney_secret_key}'
    }
    try:
        response = requests.post(api_url, data=urlencode(payload), headers=headers)
        response.raise_for_status()
        payment_data = response.json()
        if payment_data.get('status') == 'success':
            return payment_data.get('confirmation', {}).get('confirmation_url')
        else:
            print(f"Ошибка при создании платежа ЮMoney: {payment_data}")
            return None
    except requests.RequestException as e:
        print(f"Ошибка при создании платежа ЮMoney: {e}")
        print(f"Ответ сервера: {response.text}")
        return None

@login_required
def payment_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'processing'
    order.save()
    request.session['cart'] = {}  # Очищаем корзину осле успешной оплаты
    messages.success(request, "Оплата прошла успешно. Ваш заказ обрабатывается.")
    return render(request, 'nut_shop/payment_success.html', {'order': order})

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'nut_shop/order_confirmation.html', {'order': order})

@login_required
def profile(request):
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        name_form = UserNameForm(request.POST, instance=request.user)
        if profile_form.is_valid() and name_form.is_valid():
            profile_form.save()
            name_form.save()
            messages.success(request, "Профиль успешно бновлен.")
            return redirect('profile')
    else:
        profile_form = UserProfileForm(instance=user_profile)
        name_form = UserNameForm(instance=request.user)

    return render(request, 'nut_shop/profile.html', {
        'profile_form': profile_form,
        'name_form': name_form,
        'user_profile': user_profile
    })

@login_required
def change_password(request):
    if request.method == 'POST':
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        if new_password1 != new_password2:
            return JsonResponse({'error': 'Пароли не совпадают.'}, status=400)
        
        if len(new_password1) < 8:
            return JsonResponse({'error': 'Пароль должен содержать не менее 8 символов.'}, status=400)
        
        try:
            validate_password(new_password1, request.user)
        except ValidationError as e:
            return JsonResponse({'error': ' '.join(e.messages)}, status=400)
        
        user = request.user
        user.set_password(new_password1)
        user.save()
        update_session_auth_hash(request, user)  # Важно, чтобы пользователь не вышел из системы
        return JsonResponse({'success': 'Ваш пароль был успешно изменен.'})
    return JsonResponse({'error': 'Неверный метод запроса.'}, status=400)

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'nut_shop/order_history.html', {'orders': orders})

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')  # или куда вы хотите перенаправить после регистрации
    else:
        form = SignUpForm()
    return render(request, 'nut_shop/signup.html', {'form': form})

@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def payment_by_requisites(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status != 'pending_payment':
        messages.error(request, "Этот заказ уже оплачен или отменен.")
        return redirect('order_history')
    return render(request, 'nut_shop/payment_by_requisites.html', {
        'order': order,
        'bank_account': order.payment_method.bank_account
    })


@login_required
def confirm_payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == 'pending_payment':
        order.status = 'pending_payment'
        order.save()
        messages.success(request, "Оплата подтверждена. Ваш заказ орабатывается.")
    else:
        messages.error(request, "Невозможно подтвердить оплату для этого закаа.")
    return redirect('order_history')

def create_payment(order, payment_method):
    if not payment_method.shop_id or not payment_method.secret_key:
        print(f"Ошибка: отсутствует shop_id или secret_key для метода оплаты {payment_method.name}")
        return None

    Configuration.account_id = payment_method.shop_id
    Configuration.secret_key = payment_method.secret_key

    try:
        payment = Payment.create({
            "amount": {
                "value": str(order.total_price),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.SITE_DOMAIN}/payment-success/{order.id}/"
            },
            "capture": True,
            "description": f"Оплата заказа №{order.id} в Орех Маркет",
            "metadata": {
                "order_id": order.id
            }
        }, uuid.uuid4())

        return payment.confirmation.confirmation_url
    except Exception as e:
        print(f"Ошибка при создании платежа: {e}")
        return None

@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if not Order.objects.filter(user=request.user, items__product_variant__product=product, is_completed=True).exists():
        messages.error(request, 'Вы можете оставить отзыв только поле покупки товара.')
        return redirect('product_detail', pk=product_id)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
            messages.success(request, 'Ваш отыв успешн добвлен.')
            return redirect('product_detail', pk=product_id)
    else:
        form = ReviewForm()

    return render(request, 'nut_shop/add_review.html', {'form': form, 'product': product})

@login_required
def user_orders(request):
    orders = Order.objects.filter(user=request.user, status='delivered', is_completed=True)
    products_to_review = Product.objects.filter(
        variants__orderitem__order__in=orders
    ).exclude(
        reviews__user=request.user
    ).distinct()

    context = {
        'orders': orders,
        'products_to_review': products_to_review,
    }
    return render(request, 'nut_shop/user_orders.html', context)

class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'nut_shop/login.html'

@staff_member_required
def custom_admin(request):
    app_list = admin_site.get_app_list(request)
    
    # Группировка моделей по приложениям
    grouped_models = {}
    for app in app_list:
        grouped_models[app['name']] = [
            {
                'name': model['name'],
                'object_name': model['object_name'],
                'admin_url': reverse('custom_model_view', kwargs={'app_label': app['app_label'], 'model_name': model['object_name'].lower()}),
                'add_url': reverse('custom_model_add', kwargs={'app_label': app['app_label'], 'model_name': model['object_name'].lower()}),
                'app_label': app['app_label']
            }
            for model in app['models']
        ]
    
    context = {
        'grouped_models': grouped_models,
        'title': 'Панель управления Орех Маркет',
        'site_header': admin_site.site_header,
        'site_title': admin_site.site_title,
        'index_title': admin_site.index_title,
    }
    return render(request, 'admin/custom_admin.html', context)

@staff_member_required
def custom_model_view(request, app_label, model_name):
    model = apps.get_model(app_label, model_name)
    admin_class = admin_site._registry.get(model)
    
    if admin_class:
        changelist_view = admin_class.changelist_view(request)
        context = changelist_view.context_data
        context['app_label'] = app_label
        context['model_name'] = model_name
        return render(request, 'admin/custom_model_view.html', context)
    
    return render(request, 'admin/model_not_found.html', {'model_name': model_name})

@staff_member_required
def custom_model_add(request, app_label, model_name):
    model = apps.get_model(app_label, model_name)
    admin_class = admin_site._registry.get(model)
    
    if admin_class:
        add_view = admin_class.add_view(request)
        if isinstance(add_view, HttpResponseRedirect):
            # Если это реирект после успешного добавления, изменим URL
            return redirect('custom_model_view', app_label=app_label, model_name=model_name)
        context = add_view.context_data if hasattr(add_view, 'context_data') else {}
        context['app_label'] = app_label
        context['model_name'] = model_name
        return render(request, 'admin/custom_model_add.html', context)
    
    return render(request, 'admin/model_not_found.html', {'model_name': model_name})

@staff_member_required
def custom_model_change(request, app_label, model_name, object_id):
    model = apps.get_model(app_label, model_name)
    admin_class = admin_site._registry.get(model)
    
    if admin_class:
        change_view = admin_class.change_view(request, object_id)
        if isinstance(change_view, HttpResponseRedirect):
            # Если это редирект после успешного изменения, изменим URL
            return redirect('custom_model_view', app_label=app_label, model_name=model_name)
        context = change_view.context_data if hasattr(change_view, 'context_data') else {}
        context['app_label'] = app_label
        context['model_name'] = model_name
        return render(request, 'admin/custom_model_change.html', context)
    
    return render(request, 'admin/model_not_found.html', {'model_name': model_name})












