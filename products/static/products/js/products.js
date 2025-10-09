// Dokan Store JavaScript
class DokanStore {
    constructor() {
        this.cart = new DokanCart();
        this.wishlist = new DokanWishlist();
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateCartDisplay();
        this.updateWishlistDisplay();
    }

    bindEvents() {
        // Add to cart buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('add-to-cart') || 
                e.target.closest('.add-to-cart')) {
                const button = e.target.classList.contains('add-to-cart') ? e.target : e.target.closest('.add-to-cart');
                this.handleAddToCart(button);
            }
        });

        // Search functionality
        const searchForm = document.querySelector('form[action*="search"]');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                const input = searchForm.querySelector('input[name="q"]');
                if (!input.value.trim()) {
                    e.preventDefault();
                    this.showToast('Please enter a search term', 'warning');
                }
            });
        }

        // Newsletter subscription
        const newsletterForm = document.querySelector('.newsletter-form');
        if (newsletterForm) {
            newsletterForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleNewsletterSubscription(newsletterForm);
            });
        }
    }

    handleAddToCart(button) {
        const productId = button.dataset.productId;
        const productName = button.dataset.productName;
        const price = parseFloat(button.dataset.price);
        const image = button.dataset.image || '';

        this.cart.addToCart(productId, productName, price, 1, image);
        
        // Add loading state
        const originalHTML = button.innerHTML;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding...';
        button.disabled = true;

        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.disabled = false;
            this.updateCartDisplay();
        }, 1000);
    }

    handleNewsletterSubscription(form) {
        const email = form.querySelector('input[type="email"]').value;
        
        // Simulate API call
        setTimeout(() => {
            this.showToast('Thank you for subscribing to our newsletter!', 'success');
            form.reset();
        }, 1000);
    }

    updateCartDisplay() {
        const count = this.cart.getTotalItems();
        document.querySelectorAll('.cart-count').forEach(element => {
            element.textContent = count;
        });
    }

    updateWishlistDisplay() {
        const count = this.wishlist.getTotalItems();
        document.querySelectorAll('.wishlist-count').forEach(element => {
            element.textContent = count;
        });
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.top = '20px';
        toast.style.right = '20px';
        toast.style.zIndex = '9999';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}

class DokanCart {
    constructor() {
        this.key = 'dokan_cart';
        this.loadCart();
    }

    loadCart() {
        const cart = localStorage.getItem(this.key);
        this.items = cart ? JSON.parse(cart) : [];
    }

    saveCart() {
        localStorage.setItem(this.key, JSON.stringify(this.items));
    }

    addToCart(productId, productName, price, quantity = 1, image = '') {
        const existingItem = this.items.find(item => item.productId === productId);
        
        if (existingItem) {
            existingItem.quantity += quantity;
        } else {
            this.items.push({
                productId,
                productName,
                price,
                quantity,
                image,
                addedAt: new Date().toISOString()
            });
        }
        
        this.saveCart();
    }

    removeFromCart(productId) {
        this.items = this.items.filter(item => item.productId !== productId);
        this.saveCart();
    }

    updateQuantity(productId, quantity) {
        const item = this.items.find(item => item.productId === productId);
        if (item) {
            item.quantity = quantity;
            if (item.quantity <= 0) {
                this.removeFromCart(productId);
            } else {
                this.saveCart();
            }
        }
    }

    getTotalItems() {
        return this.items.reduce((total, item) => total + item.quantity, 0);
    }

    getSubtotal() {
        return this.items.reduce((total, item) => total + (item.price * item.quantity), 0);
    }

    clearCart() {
        this.items = [];
        this.saveCart();
    }
}

class DokanWishlist {
    constructor() {
        this.key = 'dokan_wishlist';
        this.loadWishlist();
    }

    loadWishlist() {
        const wishlist = localStorage.getItem(this.key);
        this.items = wishlist ? JSON.parse(wishlist) : [];
    }

    saveWishlist() {
        localStorage.setItem(this.key, JSON.stringify(this.items));
    }

    addToWishlist(productId, productName, price, image = '') {
        if (!this.items.find(item => item.productId === productId)) {
            this.items.push({
                productId,
                productName,
                price,
                image,
                addedAt: new Date().toISOString()
            });
            this.saveWishlist();
            return true;
        }
        return false;
    }

    removeFromWishlist(productId) {
        this.items = this.items.filter(item => item.productId !== productId);
        this.saveWishlist();
    }

    getTotalItems() {
        return this.items.length;
    }

    isInWishlist(productId) {
        return this.items.some(item => item.productId === productId);
    }
}

// Global functions for template use
function addToWishlist(productId) {
    const store = window.dokanStore;
    if (store.wishlist.addToWishlist(productId)) {
        store.showToast('Product added to wishlist!', 'success');
        store.updateWishlistDisplay();
    } else {
        store.showToast('Product already in wishlist', 'info');
    }
}

function quickView(productId) {
    // This would typically make an API call to get product details
    console.log('Quick view for product:', productId);
    window.dokanStore.showToast('Quick view feature coming soon!', 'info');
}

// Initialize store when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.dokanStore = new DokanStore();
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Add fade-in animation to elements
    const animateOnScroll = () => {
        const elements = document.querySelectorAll('.category-card, .product-card, .feature-icon');
        elements.forEach(element => {
            const elementTop = element.getBoundingClientRect().top;
            const elementVisible = 150;
            
            if (elementTop < window.innerHeight - elementVisible) {
                element.classList.add('fade-in-up');
            }
        });
    };

    // Initial check
    animateOnScroll();

    // Check on scroll
    window.addEventListener('scroll', animateOnScroll);
});