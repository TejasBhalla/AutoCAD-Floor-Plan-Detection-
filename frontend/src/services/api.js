import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

/**
 * Upload a floor plan image for processing.
 * @param {File} file - The image file to upload.
 * @returns {Promise<Object>} Processing result with rooms and image dimensions.
 */
export async function uploadFloorPlan(file) {
  const formData = new FormData();
  formData.append('image', file);

  const response = await api.post('/upload-floorplan/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return response.data;
}

/**
 * Save the current room layout to the backend.
 * @param {Array} rooms - Array of room objects with id, name, and polygon.
 * @returns {Promise<Object>} Save confirmation.
 */
export async function saveLayout(rooms) {
  const response = await api.post('/save-layout/', { rooms });
  return response.data;
}

/**
 * Load a previously saved layout.
 * @returns {Promise<Object>} Saved layout data.
 */
export async function loadLayout() {
  const response = await api.get('/load-layout/');
  return response.data;
}
