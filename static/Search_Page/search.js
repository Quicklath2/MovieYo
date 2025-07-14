// Search_Page/search.js
const API_URL = '/api/search';

/**
 * Performs a search and returns results in a graphical-friendly format.
 * @param {string} query - The search query.
 * @returns {Promise<Array<{title: string, image: string, description: string, type: string}>>}
 */
export async function searchMovies(query) {
    if (!query) return [];
    const res = await fetch(`${API_URL}?q=${encodeURIComponent(query)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.slice(0, 12);
} 