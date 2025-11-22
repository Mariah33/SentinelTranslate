"""
Generate sample multilingual data for batch translation examples.

This script creates a realistic parquet file with customer reviews
in multiple languages.

Usage:
    python generate_sample_data.py

Requirements:
    pip install pandas pyarrow numpy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def main():
    """Generate sample_data.parquet with multilingual reviews."""

    # Set random seed for reproducibility
    np.random.seed(42)

    # Sample reviews in different languages
    reviews = {
        'fr': [  # French
            "Excellent produit, très satisfait de mon achat.",
            "La qualité est médiocre pour le prix.",
            "Livraison rapide et service client réactif.",
            "Je recommande vivement cette entreprise.",
            "Le produit ne correspond pas à la description.",
            "Très bon rapport qualité-prix.",
            "Déçu par la qualité du matériau.",
            "Service après-vente impeccable.",
            "Le délai de livraison était trop long.",
            "Produit conforme à mes attentes.",
        ] * 5,  # Repeat to get 50 reviews

        'es': [  # Spanish
            "Excelente producto, muy satisfecho con la compra.",
            "La calidad es mediocre para el precio.",
            "Entrega rápida y servicio al cliente receptivo.",
            "Recomiendo encarecidamente esta empresa.",
            "El producto no coincide con la descripción.",
            "Muy buena relación calidad-precio.",
            "Decepcionado con la calidad del material.",
            "Servicio postventa impecable.",
            "El tiempo de entrega fue demasiado largo.",
            "Producto conforme a mis expectativas.",
        ] * 5,

        'de': [  # German
            "Ausgezeichnetes Produkt, sehr zufrieden mit dem Kauf.",
            "Die Qualität ist mittelmäßig für den Preis.",
            "Schnelle Lieferung und reaktionsschneller Kundenservice.",
            "Ich empfehle dieses Unternehmen wärmstens.",
            "Das Produkt entspricht nicht der Beschreibung.",
            "Sehr gutes Preis-Leistungs-Verhältnis.",
            "Enttäuscht von der Materialqualität.",
            "Einwandfreier Kundenservice.",
            "Die Lieferzeit war zu lang.",
            "Produkt entspricht meinen Erwartungen.",
        ] * 5,

        'zh': [  # Chinese
            "优秀的产品，对购买非常满意。",
            "质量相对于价格来说一般。",
            "交货迅速，客户服务响应快。",
            "强烈推荐这家公司。",
            "产品与描述不符。",
            "性价比很高。",
            "对材料质量感到失望。",
            "售后服务无可挑剔。",
            "交货时间太长了。",
            "产品符合我的期望。",
        ] * 5,
    }

    # Flatten reviews into single list with language tags
    all_reviews = []
    for lang, lang_reviews in reviews.items():
        for review in lang_reviews:
            all_reviews.append((review, lang))

    # Create DataFrame
    df = pd.DataFrame({
        'review_id': range(1, len(all_reviews) + 1),
        'text': [r[0] for r in all_reviews],
        'source_lang': [r[1] for r in all_reviews],
        'rating': np.random.randint(1, 6, len(all_reviews)),
        'product_category': np.random.choice(
            ['Electronics', 'Clothing', 'Home & Garden', 'Books', 'Sports & Outdoors', 'Toys'],
            len(all_reviews)
        ),
        'sentiment': np.random.choice(
            ['positive', 'negative', 'neutral'],
            len(all_reviews),
            p=[0.6, 0.25, 0.15]
        ),
        'verified_purchase': np.random.choice([True, False], len(all_reviews), p=[0.8, 0.2]),
        'helpful_count': np.random.randint(0, 100, len(all_reviews)),
        'created_at': [
            datetime.now() - timedelta(days=np.random.randint(0, 365))
            for _ in range(len(all_reviews))
        ],
    })

    # Add word count
    df['word_count'] = df['text'].str.split().str.len()

    # Save to parquet
    output_file = 'sample_data.parquet'
    df.to_parquet(output_file, index=False, engine='pyarrow')

    # Print summary
    print(f"✅ Created {output_file}")
    print(f"\n📊 Dataset Summary:")
    print(f"   Total reviews: {len(df)}")
    print(f"   Columns: {', '.join(df.columns)}")
    print(f"\n🌍 Language Distribution:")
    print(df['source_lang'].value_counts().to_string())
    print(f"\n⭐ Rating Distribution:")
    print(df['rating'].value_counts().sort_index().to_string())
    print(f"\n📦 Category Distribution:")
    print(df['product_category'].value_counts().to_string())
    print(f"\n😊 Sentiment Distribution:")
    print(df['sentiment'].value_counts().to_string())
    print(f"\n✅ Verified Purchase: {df['verified_purchase'].sum()} / {len(df)}")
    print(f"\n📝 Average Word Count: {df['word_count'].mean():.1f}")
    print(f"\n📅 Date Range: {df['created_at'].min().date()} to {df['created_at'].max().date()}")
    print(f"\nSample data:")
    print(df[['review_id', 'text', 'source_lang', 'rating', 'product_category']].head(10).to_string())
    print(f"\n🎉 Sample data generation complete!")
    print(f"   Use this file in batch_s3_example.ipynb for testing")


if __name__ == '__main__':
    try:
        main()
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("   Install dependencies: pip install pandas pyarrow numpy")
