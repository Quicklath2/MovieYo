import { searchMovies } from './search.js';

/**
 * Attaches the search UI to the given input and container.
 * @param {HTMLInputElement} inputEl - The search input element.
 * @param {HTMLElement} containerEl - The container to display results.
 */
export function attachSearchUI(inputEl, containerEl) {
    let lastQuery = '';
    let timeout = null;
    inputEl.addEventListener('input', () => {
        const query = inputEl.value.trim();
        if (timeout) clearTimeout(timeout);
        if (!query) {
            containerEl.innerHTML = '';
            return;
        }
        timeout = setTimeout(async () => {
            if (query === lastQuery) return;
            lastQuery = query;
            containerEl.innerHTML = '<div class="search-loading">Searching...</div>';
            const results = await searchMovies(query);
            if (query !== inputEl.value.trim()) return; // Ignore if input changed
            if (results.length === 0) {
                containerEl.innerHTML = '<div class="search-no-results">No results found.</div>';
                return;
            }
            containerEl.innerHTML = results.map((item, idx) => `
                <article class="search-result-card" data-id="${item.id}" data-media-type="${item.media_type}">
                    <div class="search-result-img-wrapper">
                        <img src="${item.image}" alt="${item.title}" class="search-result-img" />
                        <a class="play-btn-overlay" href="https://localhost:8000/player/${item.media_type}/${item.id}" tabindex="0" aria-label="Play ${item.title}">
                            <svg width="38" height="38" viewBox="0 0 38 38" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <circle cx="19" cy="19" r="19" fill="#e50914" fill-opacity="0.92"/>
                                <polygon points="15,12 28,19 15,26" fill="#fff"/>
                            </svg>
                        </a>
                    </div>
                    <div class="search-result-info">
                        <a class="search-result-title-link" href="https://localhost:8000/player/${item.media_type}/${item.id}" tabindex="0" aria-label="Open player for ${item.title}">${item.title}</a>
                        <div class="search-result-type">${item.type}</div>
                        <div class="search-result-desc">${item.description}</div>
                    </div>
                </article>
            `).join('');
        }, 300);
    });
} 