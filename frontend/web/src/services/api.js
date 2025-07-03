import axios from 'axios';

// Log API base URL
console.log('API Base URL:', import.meta.env.VITE_API_BASE_URL);

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Set request timeout
  timeout: 10000,
  // Allow cross-origin requests with credentials
  withCredentials: true,
});

// Add request interceptor
apiClient.interceptors.request.use(config => {
  // Do something before request is sent
  console.log('API Request:', {
    url: config.url,
    method: config.method,
    baseURL: config.baseURL,
    headers: config.headers,
  });

  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
}, error => {
  // Do something with request error
  console.error('API Request Error:', error);
  return Promise.reject(error);
});

// Add response interceptor
apiClient.interceptors.response.use(response => {
  // Do something with response data
  console.log('API Response:', {
    status: response.status,
    statusText: response.statusText,
    data: response.data,
  });
  return response;
}, error => {
  // Do something with response error
  console.error('API Response Error:', error);
  if (error.response) {
    // Request was made and server responded with status code outside of 2xx range
    console.error('Error Response Data:', error.response.data);
    console.error('Error Response Status:', error.response.status);
    console.error('Error Response Headers:', error.response.headers);
  } else if (error.request) {
    // Request was made but no response received
    console.error('Error Request:', error.request);
  } else {
    // Something happened in setting up the request that triggered an error
    console.error('Error Message:', error.message);
  }
  return Promise.reject(error);
});

export const getBots = (token) => {
  // Call bots_service through Vite proxy at /api/bots
  return axios.get('/api/bots', {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }).then(response => {
    // Transform bots_service response format to match expected format
    if (response.data && response.data.status === 'success') {
      return { data: response.data.data }; // Extract the actual bot array
    } else {
      throw new Error(response.data?.message || 'Failed to get bots');
    }
  });
};

export default apiClient;