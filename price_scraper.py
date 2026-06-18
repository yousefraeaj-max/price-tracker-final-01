import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin

class PriceScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def extract_price(self, url):
        """Extract price from a product page using multiple methods"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Method 1: JSON-LD structured data
            price = self._extract_from_json_ld(soup)
            if price:
                return price
            
            # Method 2: Meta tags (OpenGraph, Product)
            price = self._extract_from_meta_tags(soup)
            if price:
                return price
            
            # Method 3: Data attributes
            price = self._extract_from_data_attributes(soup)
            if price:
                return price
            
            # Method 4: Common class names and patterns
            price = self._extract_from_classes(soup)
            if price:
                return price
            
            # Method 5: Text patterns (currency + numbers)
            price = self._extract_from_text_patterns(soup)
            if price:
                return price
            
            return None
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def _extract_from_json_ld(self, soup):
        """Extract price from JSON-LD structured data"""
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        price = self._get_price_from_json(item)
                        if price:
                            return price
                else:
                    price = self._get_price_from_json(data)
                    if price:
                        return price
            except:
                continue
        return None
    
    def _get_price_from_json(self, data):
        """Extract price from JSON object"""
        if isinstance(data, dict):
            # Check for price field
            for key in ['price', 'offers', 'lowPrice', 'highPrice']:
                if key in data:
                    if key == 'offers':
                        if isinstance(data[key], list) and len(data[key]) > 0:
                            offer = data[key][0]
                            if 'price' in offer:
                                return self._clean_price(offer['price'])
                        elif isinstance(data[key], dict):
                            if 'price' in data[key]:
                                return self._clean_price(data[key]['price'])
                    else:
                        return self._clean_price(data[key])
        return None
    
    def _extract_from_meta_tags(self, soup):
        """Extract price from meta tags"""
        meta_patterns = [
            ('property', 'product:price:amount'),
            ('property', 'og:price:amount'),
            ('name', 'price'),
            ('property', 'price'),
        ]
        
        for attr_name, attr_value in meta_patterns:
            meta = soup.find('meta', attrs={attr_name: attr_value})
            if meta and meta.get('content'):
                price = self._clean_price(meta['content'])
                if price:
                    return price
        return None
    
    def _extract_from_data_attributes(self, soup):
        """Extract price from data attributes"""
        # Common data attribute patterns
        patterns = [
            'data-price',
            'data-product-price',
            'data-current-price',
            'data-sale-price',
        ]
        
        for pattern in patterns:
            element = soup.find(attrs={pattern: True})
            if element:
                price = self._clean_price(element.get(pattern))
                if price:
                    return price
        return None
    
    def _extract_from_classes(self, soup):
        """Extract price from common class names"""
        class_patterns = [
            'price',
            'product-price',
            'current-price',
            'sale-price',
            'regular-price',
            'amount',
            'price-value',
            'product__price',
            'price__amount',
        ]
        
        for pattern in class_patterns:
            elements = soup.find_all(class_=re.compile(pattern, re.I))
            for element in elements:
                text = element.get_text(strip=True)
                price = self._clean_price(text)
                if price:
                    return price
        return None
    
    def _extract_from_text_patterns(self, soup):
        """Extract price using currency + number patterns"""
        # Common currency symbols and codes
        currency_patterns = [
            r'[\$£€]\s*[\d,]+\.?\d*',  # $, £, € with numbers
            r'EGP\s*[\d,]+\.?\d*',     # EGP with numbers
            r'ج\.م\.\s*[\d,]+\.?\d*',  # ج.م. with numbers
            r'LE\s*[\d,]+\.?\d*',      # LE with numbers
            r'[\d,]+\.?\d*\s*(ج\.م\.|EGP|LE)',  # Numbers followed by currency
        ]
        
        text = soup.get_text()
        for pattern in currency_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for match in matches:
                    price = self._clean_price(match)
                    if price and price > 0:
                        return price
        return None
    
    def _clean_price(self, price_str):
        """Clean and convert price string to float"""
        if not price_str:
            return None
        
        # Remove currency symbols and text
        price_str = re.sub(r'[^\d.,]', '', str(price_str))
        
        if not price_str:
            return None
        
        # Handle different decimal separators
        if ',' in price_str and '.' in price_str:
            # Assume last separator is decimal
            if price_str.rindex(',') > price_str.rindex('.'):
                price_str = price_str.replace('.', '').replace(',', '.')
            else:
                price_str = price_str.replace(',', '')
        elif ',' in price_str:
            # Check if comma is decimal separator (European style)
            parts = price_str.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                price_str = price_str.replace(',', '.')
            else:
                price_str = price_str.replace(',', '')
        
        try:
            return float(price_str)
        except:
            return None
