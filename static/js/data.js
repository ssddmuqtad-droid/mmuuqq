// ===== Sample Data =====
const INITIAL_PROPERTIES = [
  {
    id: 1,
    type: 'house',
    status: 'ready',
    location: 'المنصور، بغداد',
    area: 250,
    price: 350000000,
    description: 'بيت حديث البناء في المنصور، قرب سوق السيدية، يحتوي على 4 غرف نوم، صالة كبيرة، حديقة أمامية.',
    images: [],
    phone: '',
    date: '2026-04-01'
  },
  {
    id: 2,
    type: 'land',
    status: 'ready',
    location: 'الكرادة، بغداد',
    area: 500,
    price: 200000000,
    description: 'قطعة أرض استثمارية في الكرادة، قريبة من الشارع الرئيسي، مناسبة للبناء التجاري.',
    images: [],
    phone: '',
    date: '2026-04-05'
  },
  {
    id: 3,
    type: 'building',
    status: 'under-construction',
    location: 'الجادرية، بغداد',
    area: 1200,
    price: 950000000,
    description: 'بناية سكنية قيد الإنشاء في الجادرية، 6 طوابق، موقع مميز قرب الجامعة.',
    images: [],
    phone: '',
    date: '2026-04-10'
  },
  {
    id: 4,
    type: 'house',
    status: 'ready',
    location: 'الدورة، بغداد',
    area: 180,
    price: 180000000,
    description: 'بيت عائلي في الدورة، مجدد بالكامل، 3 غرف، مطبخ جديد، موقف سيارة.',
    images: [],
    phone: '',
    date: '2026-04-12'
  },
  {
    id: 5,
    type: 'land',
    status: 'ready',
    location: 'الأعظمية، بغداد',
    area: 300,
    price: 120000000,
    description: 'قطعة أرض سكنية في الأعظمية، حي هادئ، خدمات متوفرة.',
    images: [],
    phone: '',
    date: '2026-04-15'
  },
  {
    id: 6,
    type: 'building',
    status: 'ready',
    location: 'الكرخ، بغداد',
    area: 800,
    price: 680000000,
    description: 'بناية تجارية جاهزة في الكرخ، 4 طوابق، مناسبة للمكاتب أو المحلات.',
    images: [],
    phone: '',
    date: '2026-04-18'
  }
];

const INITIAL_MESSAGES = [
  {
    id: 1,
    name: 'محمد أحمد',
    message: 'أهلاً، هل يمكنني الحصول على معلومات أكثر عن البيت في المنصور؟',
    propertyId: 1,
    date: '2026-04-20'
  },
  {
    id: 2,
    name: 'فاطمة علي',
    message: 'هل الأرض في الكرادة قريبة من المواصلات العامة؟',
    propertyId: 2,
    date: '2026-04-21'
  }
];

// ===== Storage Functions =====
function getProperties() {
  const stored = localStorage.getItem('properties');
  return stored ? JSON.parse(stored) : INITIAL_PROPERTIES;
}

function saveProperties(properties) {
  localStorage.setItem('properties', JSON.stringify(properties));
}

function getMessages() {
  const stored = localStorage.getItem('messages');
  return stored ? JSON.parse(stored) : INITIAL_MESSAGES;
}

function saveMessages(messages) {
  localStorage.setItem('messages', JSON.stringify(messages));
}

function addProperty(property) {
  const properties = getProperties();
  property.id = Date.now();
  property.date = new Date().toISOString().split('T')[0];
  property.images = property.images ? property.images.split(',').map(img => img.trim()) : [];
  properties.unshift(property);
  saveProperties(properties);
  return property;
}

function updateProperty(id, updates) {
  const properties = getProperties();
  const index = properties.findIndex(p => p.id === id);
  if (index !== -1) {
    properties[index] = { ...properties[index], ...updates };
    if (updates.images) {
      properties[index].images = updates.images.split(',').map(img => img.trim());
    }
    saveProperties(properties);
    return properties[index];
  }
  return null;
}

function deleteProperty(id) {
  const properties = getProperties();
  const filtered = properties.filter(p => p.id !== id);
  saveProperties(filtered);
  return filtered.length < properties.length;
}

function addMessage(message) {
  const messages = getMessages();
  message.id = Date.now();
  message.date = new Date().toISOString().split('T')[0];
  messages.unshift(message);
  saveMessages(messages);
  return message;
}
