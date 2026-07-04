// ===== Global State =====
let favorites = JSON.parse(localStorage.getItem('favorites') || '[]');
let compareList = JSON.parse(localStorage.getItem('compareList') || '[]');
let recentViews = JSON.parse(localStorage.getItem('recentViews') || '[]');

// ===== UI Functions =====
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.style.cssText = 'background:var(--card-bg);padding:1rem;margin-bottom:0.5rem;border-radius:8px;box-shadow:var(--shadow);border-right:4px solid var(--primary)';
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function formatPrice(price) {
  return new Intl.NumberFormat('ar-IQ').format(price) + ' د.ع';
}

// ===== Favorites =====
function toggleFavorite(id, url, title) {
  const index = favorites.findIndex(f => f.id === id);
  if (index > -1) {
    favorites.splice(index, 1);
    showToast('تم الإزالة من المفضلة');
  } else {
    favorites.push({ id, url, title });
    showToast('تمت الإضافة إلى المفضلة');
  }
  localStorage.setItem('favorites', JSON.stringify(favorites));
  updateFavoriteButtons();
  updateFavoritesGrid();
}

function updateFavoriteButtons() {
  document.querySelectorAll('.btn-favorite').forEach(btn => {
    const id = parseInt(btn.dataset.favId);
    if (favorites.some(f => f.id === id)) {
      btn.textContent = '❤️';
    } else {
      btn.textContent = '🤍';
    }
  });
}

function updateFavoritesGrid() {
  const grid = document.getElementById('favorites-grid');
  const section = document.getElementById('favorites-section');
  const count = document.getElementById('fav-count');
  
  if (count) {
    count.textContent = favorites.length;
    count.hidden = favorites.length === 0;
  }
  
  if (!grid || favorites.length === 0) {
    if (section) section.style.display = 'none';
    return;
  }
  
  section.style.display = 'block';
  grid.innerHTML = favorites.map(fav => `
    <div class="property-card">
      <a href="${fav.url}" class="property-card-body">
        <h3 class="property-card-title">${fav.title}</h3>
      </a>
    </div>
  `).join('');
}

// ===== Compare =====
function toggleCompare(id, url, title, price, area, city, type) {
  const index = compareList.findIndex(c => c.id === id);
  if (index > -1) {
    compareList.splice(index, 1);
    showToast('تم الإزالة من المقارنة');
  } else {
    if (compareList.length >= 3) {
      showToast('يمكنك مقارنة 3 عقارات كحد أقصى', 'error');
      return;
    }
    compareList.push({ id, url, title, price, area, city, type });
    showToast('تمت الإضافة للمقارنة');
  }
  localStorage.setItem('compareList', JSON.stringify(compareList));
  updateCompareBar();
}

function updateCompareBar() {
  const bar = document.getElementById('compare-bar');
  const count = document.getElementById('compare-count');
  
  if (!bar) return;
  
  if (compareList.length === 0) {
    bar.hidden = true;
  } else {
    bar.hidden = false;
    count.textContent = `${compareList.length} عقارات للمقارنة`;
  }
}

function clearCompare() {
  compareList = [];
  localStorage.setItem('compareList', JSON.stringify(compareList));
  updateCompareBar();
  showToast('تم مسح قائمة المقارنة');
}

function openCompareModal() {
  const modal = document.getElementById('compare-modal');
  const content = document.getElementById('compare-content');
  
  if (!modal || !content) return;
  
  if (compareList.length === 0) {
    showToast('لا توجد عقارات للمقارنة', 'error');
    return;
  }
  
  content.innerHTML = `
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <th style="padding:0.5rem;border-bottom:1px solid var(--border)">العقار</th>
        <th style="padding:0.5rem;border-bottom:1px solid var(--border)">السعر</th>
        <th style="padding:0.5rem;border-bottom:1px solid var(--border)">المساحة</th>
        <th style="padding:0.5rem;border-bottom:1px solid var(--border)">المدينة</th>
      </tr>
      ${compareList.map(item => `
        <tr>
          <td style="padding:0.5rem;border-bottom:1px solid var(--border)">${item.title}</td>
          <td style="padding:0.5rem;border-bottom:1px solid var(--border)">${item.price}</td>
          <td style="padding:0.5rem;border-bottom:1px solid var(--border)">${item.area} م²</td>
          <td style="padding:0.5rem;border-bottom:1px solid var(--border)">${item.city}</td>
        </tr>
      `).join('')}
    </table>
  `;
  
  modal.style.display = 'block';
}

// ===== Recent Views =====
function addToRecent(id, url, title) {
  recentViews = recentViews.filter(r => r.id !== id);
  recentViews.unshift({ id, url, title });
  if (recentViews.length > 10) recentViews.pop();
  localStorage.setItem('recentViews', JSON.stringify(recentViews));
  updateRecentGrid();
}

function updateRecentGrid() {
  const grid = document.getElementById('recent-grid');
  const section = document.getElementById('recent-section');
  
  if (!grid || recentViews.length === 0) {
    if (section) section.style.display = 'none';
    return;
  }
  
  section.style.display = 'block';
  grid.innerHTML = recentViews.map(view => `
    <div class="property-card">
      <a href="${view.url}" class="property-card-body">
        <h3 class="property-card-title">${view.title}</h3>
      </a>
    </div>
  `).join('');
}

// ===== Search =====
function updateCityList(province) {
  const datalist = document.getElementById('city-list');
  if (!datalist || !window.GOVERNORATE_CITIES) return;
  
  const cities = window.GOVERNORATE_CITIES[province] || [];
  datalist.innerHTML = cities.map(city => `<option value="${city}">`).join('');
}

// ===== Gallery =====
function initGallery() {
  const mainImg = document.getElementById('gallery-main-img');
  const thumbs = document.querySelectorAll('.gallery-thumbs img');
  const prevBtn = document.querySelector('.gallery-nav.prev');
  const nextBtn = document.querySelector('.gallery-nav.next');
  
  if (!mainImg || thumbs.length === 0) return;
  
  let currentIndex = 0;
  const images = Array.from(thumbs).map(img => img.dataset.full);
  
  thumbs.forEach((thumb, index) => {
    thumb.addEventListener('click', () => {
      currentIndex = index;
      mainImg.src = images[index];
    });
  });
  
  if (prevBtn) {
    prevBtn.addEventListener('click', () => {
      currentIndex = (currentIndex - 1 + images.length) % images.length;
      mainImg.src = images[currentIndex];
    });
  }
  
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      currentIndex = (currentIndex + 1) % images.length;
      mainImg.src = images[currentIndex];
    });
  }
}

// ===== Calculator =====
function initCalculator() {
  const slider = document.getElementById('calc-years');
  const display = document.getElementById('calc-years-val');
  const result = document.getElementById('calc-monthly');
  
  if (!slider || !display || !result || !window.PROPERTY_PRICE) return;
  
  slider.addEventListener('input', () => {
    const years = parseInt(slider.value);
    display.textContent = `${years} سنة`;
    const monthly = Math.round(window.PROPERTY_PRICE / (years * 12));
    result.textContent = `${formatPrice(monthly)} شهرياً`;
  });
  
  // Initial calculation
  const years = parseInt(slider.value);
  const monthly = Math.round(window.PROPERTY_PRICE / (years * 12));
  result.textContent = `${formatPrice(monthly)} شهرياً`;
}

// ===== Map =====
function initPropertyMap() {
  const mapEl = document.getElementById('property-map');
  if (!mapEl || !mapEl.dataset.lat || !mapEl.dataset.lng) return;
  
  const lat = parseFloat(mapEl.dataset.lat);
  const lng = parseFloat(mapEl.dataset.lng);
  
  if (typeof L !== 'undefined') {
    const map = L.map(mapEl).setView([lat, lng], 15);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap'
    }).addTo(map);
    L.marker([lat, lng]).addTo(map);
  }
}

// ===== Theme Toggle - DISABLED (Force Dark Mode) =====
function initThemeToggle() {
  // Theme toggle disabled - always use dark mode
  document.documentElement.setAttribute('data-theme', 'dark');
  localStorage.setItem('theme', 'dark');
}

// ===== Back to Top =====
function initBackToTop() {
  const btn = document.getElementById('back-to-top');
  if (!btn) return;
  
  window.addEventListener('scroll', () => {
    btn.style.display = window.scrollY > 300 ? 'block' : 'none';
  });
  
  btn.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

// ===== Mobile Navigation =====
function initMobileNav() {
  const toggle = document.querySelector('.hamburger') || document.querySelector('.nav-toggle');
  const links = document.querySelector('.nav-links');

  if (!toggle || !links) return;

  const closeMenu = () => {
    toggle.classList.remove('active');
    links.classList.remove('active');
    toggle.setAttribute('aria-expanded', 'false');
  };

  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    toggle.classList.toggle('active');
    links.classList.toggle('active');
    toggle.setAttribute('aria-expanded', links.classList.contains('active'));
  });

  document.addEventListener('click', (e) => {
    if (!toggle.contains(e.target) && !links.contains(e.target)) {
      closeMenu();
    }
  });

  links.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', closeMenu);
  });
}

// ===== Search Panel Toggle =====
function initSearchToggle() {
  const toggle = document.getElementById('search-toggle');
  const panel = document.getElementById('search');
  
  if (!toggle || !panel) return;
  
  toggle.addEventListener('click', () => {
    panel.classList.toggle('collapsed');
  });
}

// ===== Province Change =====
function initProvinceSelect() {
  const provinceSelect = document.getElementById('id_province');
  if (!provinceSelect) return;
  
  provinceSelect.addEventListener('change', () => {
    updateCityList(provinceSelect.value);
  });
  
  // Initialize on load
  updateCityList(provinceSelect.value);
}

// ===== Dashboard Tabs =====
function initDashboardTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.panel');
  
  if (tabs.length === 0) return;
  
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      
      tabs.forEach(t => t.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));
      
      tab.classList.add('active');
      document.getElementById(`panel-${target}`).classList.add('active');
    });
  });
}

// ===== Compare Modal Close =====
function initCompareModal() {
  const modal = document.getElementById('compare-modal');
  const closeBtn = document.getElementById('compare-close');
  
  if (!modal || !closeBtn) return;
  
  closeBtn.addEventListener('click', () => {
    modal.style.display = 'none';
  });
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.style.display = 'none';
    }
  });
}

// ===== Share Button =====
function initShareButton() {
  const btn = document.getElementById('btn-share');
  if (!btn) return;
  
  btn.addEventListener('click', async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: document.title,
          url: window.location.href
        });
      } catch (err) {
        // User cancelled
      }
    } else {
      navigator.clipboard.writeText(window.location.href);
      showToast('تم نسخ الرابط');
    }
  });
}

// ===== Active Navigation =====
function initActiveNav() {
  const path = window.location.pathname;
  const hash = window.location.hash;

  document.querySelectorAll('.nav-links a[data-nav], .bottom-nav-item[data-nav]').forEach((link) => {
    const nav = link.dataset.nav;
    let isActive = false;

    if (nav === 'home' && (path === '/' || path === '/home/')) isActive = true;
    else if (nav === 'explore' && path.startsWith('/explore')) isActive = true;
    else if (nav === 'about' && path.startsWith('/about')) isActive = true;
    else if (nav === 'contact' && path.startsWith('/contact')) isActive = true;
    else if (nav === 'dashboard' && path.startsWith('/dashboard')) isActive = true;
    else if (nav === 'login' && path.startsWith('/login')) isActive = true;
    else if (nav === 'messaging' && path.includes('messag')) isActive = true;
    else if (nav === 'settings' && path.startsWith('/settings')) isActive = true;

    link.classList.toggle('active', isActive);
  });
}

// ===== Scroll Reveal =====
function initScrollReveal() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const targets = document.querySelectorAll(
    '.property-card, .stat-card, .card, .hero-quick-search, .filters-section, .section-header'
  );
  targets.forEach((el) => el.classList.add('reveal'));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
  );

  document.querySelectorAll('.reveal').forEach((el) => observer.observe(el));
}

// ===== Property Rendering =====
function initApp() {
  updateFavoriteButtons();
  updateFavoritesGrid();
  updateRecentGrid();
  updateCompareBar();
  initGallery();
  initCalculator();
  initPropertyMap();
  initThemeToggle();
  initBackToTop();
  initMobileNav();
  initActiveNav();
  initScrollReveal();
  initSearchToggle();
  initProvinceSelect();
  initDashboardTabs();
  initCompareModal();
  initShareButton();
}

function renderProperties(properties) {
  const grid = document.getElementById('properties-grid');
  const noResults = document.getElementById('no-results');
  
  if (!grid) return;
  
  if (!properties || properties.length === 0) {
    grid.innerHTML = '';
    if (noResults) noResults.style.display = 'block';
    return;
  }
  
  if (noResults) noResults.style.display = 'none';
  
  grid.innerHTML = properties.map(prop => `
    <div class="property-card" data-property-id="${prop.id}" data-property-url="${prop.url || '#'}" data-property-title="${prop.title || prop.display_title || ''}">
      <div class="property-image-wrapper">
        ${prop.image ? `<img src="${prop.image}" alt="${prop.title || prop.display_title}" class="property-image">` : '<div class="property-image-placeholder">🏠</div>'}
      </div>
      <div class="property-info">
        <span class="property-type type-${prop.type || 'house'}">${prop.type_display || prop.type || 'عقار'}</span>
        <h3 class="property-title">${prop.title || prop.display_title || ''}</h3>
        <div class="property-meta">
          <span>📍 ${prop.location || prop.city || ''}</span>
          <span>📐 ${prop.area || 0} م²</span>
        </div>
        <div class="property-price">${formatPrice(prop.price || 0)}</div>
      </div>
    </div>
  `).join('');
}

function getFilteredProperties() {
  const type = document.getElementById('filter-type')?.value || '';
  const status = document.getElementById('filter-status')?.value || '';
  const priceMin = parseInt(document.getElementById('filter-price-min')?.value) || 0;
  const priceMax = parseInt(document.getElementById('filter-price-max')?.value) || Infinity;
  const location = document.getElementById('filter-location')?.value?.toLowerCase() || '';
  
  let properties = window.PROPERTIES_DATA || [];
  
  return properties.filter(prop => {
    if (type && prop.type !== type) return false;
    if (status && prop.status !== status) return false;
    if (prop.price < priceMin || prop.price > priceMax) return false;
    if (location && !prop.location?.toLowerCase().includes(location) && !prop.city?.toLowerCase().includes(location)) return false;
    return true;
  });
}

function applyFilters() {
  const filtered = getFilteredProperties();
  renderProperties(filtered);
}

function resetFilters() {
  document.getElementById('filter-type').value = '';
  document.getElementById('filter-status').value = '';
  document.getElementById('filter-price-min').value = '';
  document.getElementById('filter-price-max').value = '';
  document.getElementById('filter-location').value = '';
  renderProperties(window.PROPERTIES_DATA || []);
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = 'block';
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = 'none';
}

function handleLogin(event) {
  event.preventDefault();
  // Form is submitted normally via Django's form handling
  // No JavaScript intervention needed
}

function handleContact(event) {
  event.preventDefault();
  const name = document.getElementById('contact-name')?.value;
  const message = document.getElementById('contact-message')?.value;
  
  if (name && message) {
    showToast('تم إرسال رسالتك بنجاح', 'success');
    closeModal('contactModal');
    document.getElementById('contactForm')?.reset();
  } else {
    showToast('يرجى تعبئة جميع الحقول', 'error');
  }
}

function logout() {
  showToast('تم تسجيل الخروج', 'info');
  window.location.href = '/';
}

// ===== Dashboard Functions =====
function renderDashboardProperties() {
  const container = document.getElementById('dashboard-properties');
  if (!container) return;
  
  const properties = window.DASHBOARD_PROPERTIES || [];
  
  if (properties.length === 0) {
    container.innerHTML = '<p class="no-results">لا توجد عقارات</p>';
    return;
  }
  
  container.innerHTML = properties.map(prop => `
    <div class="dashboard-item">
      ${prop.image ? `<img src="${prop.image}" alt="${prop.display_title}">` : '<div class="item-thumb">🏠</div>'}
      <div class="item-info">
        <div class="item-title">${prop.display_title}</div>
        <div class="item-meta">${prop.type_display} - ${prop.status_display} - ${formatPrice(prop.price)}</div>
      </div>
      <div class="item-actions">
        <button class="btn btn-sm btn-primary" onclick="window.location.href='${prop.url}'">تعديل</button>
        <button class="btn btn-sm btn-danger" onclick="deleteProperty(${prop.id})">حذف</button>
      </div>
    </div>
  `).join('');
}

function renderMessages() {
  const container = document.getElementById('messages-list');
  if (!container) return;
  
  const messages = window.MESSAGES || [];
  
  if (messages.length === 0) {
    container.innerHTML = '<p class="no-results">لا توجد رسائل</p>';
    return;
  }
  
  container.innerHTML = messages.map(msg => `
    <div class="dashboard-item" style="${msg.is_read ? 'opacity: 0.6' : ''}">
      <div class="item-info">
        <div class="item-title">${msg.name}</div>
        <div class="item-meta">${msg.created_at} - ${msg.phone || ''}</div>
        <div style="margin-top: 8px; color: var(--text-light);">${msg.message}</div>
      </div>
      <div class="item-actions">
        ${!msg.is_read ? `<button class="btn btn-sm btn-success" onclick="markAsRead('${msg.mark_read_url}')">تعليم كمقروء</button>` : ''}
      </div>
    </div>
  `).join('');
}

function deleteProperty(id) {
  if (confirm('هل أنت متأكد من حذف هذا العقار؟')) {
    // In a real app, this would make an API call
    showToast('تم حذف العقار', 'success');
    // Reload the page to reflect changes
    window.location.reload();
  }
}

function markAsRead(url) {
  window.location.href = url;
}

function handleAddProperty(event) {
  event.preventDefault();
  // In a real app, this would submit to the Django backend
  showToast('تم نشر العقار بنجاح', 'success');
  document.getElementById('addPropertyForm').reset();
  window.location.reload();
}

function handleEditProperty(event) {
  event.preventDefault();
  // In a real app, this would submit to the Django backend
  showToast('تم تحديث العقار بنجاح', 'success');
  closeModal('editModal');
  window.location.reload();
}

// ===== Property Detail =====
function renderPropertyDetail() {
  const container = document.getElementById('property-detail');
  if (!container) return;
  
  const prop = window.PROPERTY_DETAIL;
  if (!prop) return;
  
  container.innerHTML = `
    <div class="detail-gallery-placeholder">
      ${prop.images && prop.images.length > 0 ? `<img src="${prop.images[0]}" alt="${prop.display_title}" style="width:100%;height:100%;object-fit:cover;">` : '🏠'}
    </div>
    <div class="detail-body">
      <div class="detail-header">
        <h1 class="detail-title">${prop.display_title}</h1>
        <span class="property-type type-${prop.type}">${prop.type_display}</span>
      </div>
      
      <div class="detail-meta-grid">
        <div class="detail-meta-item">
          <div class="detail-meta-label">السعر</div>
          <div class="detail-meta-value">${prop.price_formatted}</div>
        </div>
        <div class="detail-meta-item">
          <div class="detail-meta-label">المساحة</div>
          <div class="detail-meta-value">${prop.area} م²</div>
        </div>
        <div class="detail-meta-item">
          <div class="detail-meta-label">الموقع</div>
          <div class="detail-meta-value">${prop.city} - ${prop.district || ''}</div>
        </div>
        <div class="detail-meta-item">
          <div class="detail-meta-label">الحالة</div>
          <div class="detail-meta-value">${prop.status_display}</div>
        </div>
        ${prop.bedrooms ? `
        <div class="detail-meta-item">
          <div class="detail-meta-label">الغرف</div>
          <div class="detail-meta-value">${prop.bedrooms}</div>
        </div>
        ` : ''}
        ${prop.bathrooms ? `
        <div class="detail-meta-item">
          <div class="detail-meta-label">الحمامات</div>
          <div class="detail-meta-value">${prop.bathrooms}</div>
        </div>
        ` : ''}
        ${prop.floors ? `
        <div class="detail-meta-item">
          <div class="detail-meta-label">الطوابق</div>
          <div class="detail-meta-value">${prop.floors}</div>
        </div>
        ` : ''}
      </div>
      
      <div class="detail-desc">
        <h3>الوصف</h3>
        <p>${prop.description}</p>
      </div>
      
      <div style="margin-top: 30px;">
        <button class="btn btn-primary" onclick="openModal('contactModal')">تواصل مع الدلال</button>
        <div class="broker-phone">${prop.broker_phone}</div>
      </div>
    </div>
  `;
}

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
  initApp();
  
  // Track property view
  const propertyCard = document.querySelector('.property-card[data-property-url]');
  if (propertyCard) {
    const id = parseInt(propertyCard.dataset.propertyId);
    const url = propertyCard.dataset.propertyUrl;
    const title = propertyCard.dataset.propertyTitle;
    if (id && url && title) {
      addToRecent(id, url, title);
    }
  }
  
  // Event delegation for dynamic elements
  document.addEventListener('click', (e) => {
    const favBtn = e.target.closest('.btn-favorite');
    if (favBtn) {
      e.preventDefault();
      toggleFavorite(
        parseInt(favBtn.dataset.favId),
        favBtn.dataset.favUrl,
        favBtn.dataset.favTitle
      );
    }
    
    const compareBtn = e.target.closest('.btn-compare-add');
    if (compareBtn) {
      e.preventDefault();
      toggleCompare(
        parseInt(compareBtn.dataset.compareId),
        compareBtn.dataset.compareUrl,
        compareBtn.dataset.compareTitle,
        compareBtn.dataset.comparePrice,
        compareBtn.dataset.compareArea,
        compareBtn.dataset.compareCity,
        compareBtn.dataset.compareType
      );
    }
  });
  
  document.getElementById('compare-clear')?.addEventListener('click', clearCompare);
  document.getElementById('compare-open')?.addEventListener('click', openCompareModal);
});
