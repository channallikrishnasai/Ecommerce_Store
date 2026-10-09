from django import forms

from cart.models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'title',
            'image',
            'description',
            'price',
            'stock',
            'active',
            'primary_category',
            'secondary_categories',
            'available_colours',
            'available_sizes',
        ]


__all__ = ('ProductForm',)
