from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def dodla_products(request):
    """View to display all Dodla dairy products."""
    # Group products by category
    categorized_products = {
        'Milk': [
            {'name': 'Full Cream Milk 500 ML', 'image': 'Dodla/FCM.png', 'description': 'Full Cream Milk, packed with nutrients and natural goodness.'},
            {'name': 'Full Cream Milk 130 ML', 'image': 'Dodla/FCM-130.png', 'description': 'Full Cream Milk in 130g packs, rich and creamy for daily use.'},
            {'name': 'Standardized Milk Gold', 'image': 'Dodla/STM-Gold.png', 'description': 'Standardized Milk Gold, premium quality with golden standards.'},
            {'name': 'UHT Double Toned Milk', 'image': 'Dodla/UHT-Double-Toned-Milk.webp', 'description': 'Ultra High Temperature processed double toned milk, long shelf life.'},
        ],
        'Curd': [
            {'name': 'Curd 500 GMS', 'image': 'Dodla/Curd.png', 'description': 'Traditional homemade-style curd, smooth and delicious.'},
            {'name': 'Curd 130g', 'image': 'Dodla/Curd-130.png', 'description': 'Fresh curd in 130g packs, rich in probiotics for digestive health.'},
            {'name': 'Curd Bucket Double Toned Milk', 'image': 'Dodla/Curd-bucket-DTM.png', 'description': 'Double Toned Milk curd in bulk buckets, great for families and events.'},
            {'name': 'Curd Bucket Toned Milk', 'image': 'Dodla/Curd-bucket-tm.png', 'description': 'Toned Milk curd in large buckets, creamy and nutritious.'},
            {'name': 'Curd Cup', 'image': 'Dodla/Curd-cup.png', 'description': 'Individual curd cups for easy consumption, fresh and hygienic.'},
        ],
        'Ghee': [
            {'name': 'Ghee', 'image': 'Dodla/Ghee.webp', 'description': 'Clarified butter ghee, essential for authentic Indian cuisine.'},
            {'name': 'Cow Ghee', 'image': 'Dodla/Cow-Ghee.webp', 'description': 'Pure cow ghee made from traditional methods, ideal for cooking and flavoring.'},
        ],
        'Butter Milk & Lassi': [
            {'name': 'Butter Milk Packet', 'image': 'Dodla/buter-milk-packet.png', 'description': 'Refreshing buttermilk in convenient packets, perfect for a healthy drink.'},
            {'name': 'Sweet Lassi', 'image': 'Dodla/Sweet-Lassi.png', 'description': 'Sweetened yogurt drink, refreshing and nutritious.'},
        ],
        'Sweets & Desserts': [
            {'name': 'Doodh Peda 200 GMS', 'image': 'Dodla/Doodh-Peda.png', 'description': 'Sweet milk-based peda, a delightful Indian sweet treat.'},
            {'name': 'Junnu', 'image': 'Dodla/Junnu.png', 'description': 'Traditional Andhra sweet made from milk, soft and flavorful.'},
            {'name': 'Soan Papdi 200 GMS', 'image': 'Dodla/Soan-Papdi.png', 'description': 'Crispy and sweet soan papdi, a popular Indian confection.'},
        ],
        'Other Dairy Products': [
            {'name': 'Paneer', 'image': 'Dodla/paneer-1.png', 'description': 'Fresh paneer cubes, perfect for vegetarian dishes and curries.'},
            {'name': 'Flavoured Milk', 'image': 'Dodla/flm.png', 'description': 'Full Life Milk, long-lasting freshness with premium quality.'},
        ],
    }
    
    context = {
        'categorized_products': categorized_products,
    }
    
    return render(request, 'milk_agency/dodla_products.html', context)
