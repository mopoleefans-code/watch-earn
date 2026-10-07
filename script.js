document.addEventListener('DOMContentLoaded', () => {
  const navItems = document.querySelectorAll('.nav-item');
  const segments = document.querySelectorAll('.segment');
  const panels = document.querySelectorAll('[data-panel]');
  const upgradeBox = document.querySelector('.upgrade-box');
  const upgradeButton = upgradeBox ? upgradeBox.querySelector('button') : null;
  const walletStatus = document.getElementById('wallet-payment-status');
  const upgradeStatus = document.getElementById('upgrade-payment-status');
  const walletAmountInput = document.getElementById('topup-amount');
  const walletCheckoutButton = document.getElementById('wallet-checkout-btn');
  const bookingForm = document.getElementById('booking-form');
  const bookingStatus = document.getElementById('booking-status');
  const seatButtons = document.querySelectorAll('.seat');
  const fxResult = document.getElementById('fx-result');
  const exchangeAmount = document.getElementById('exchange-amount');
  const exchangeCurrency = document.getElementById('exchange-currency');
  const convertRateButton = document.getElementById('convert-rate');
  const narrationButton = document.getElementById('demo-narration-btn');
  const narrationVoiceSelect = document.getElementById('demo-narration-voice');
  const narrationStatus = document.getElementById('demo-narration-status');
  const shareButton = document.getElementById('share-demo-btn');
  const shareStatus = document.getElementById('share-demo-status');
  const cinemaPreview = document.querySelector('.cinema-preview-video');
  const settingsStatus = document.getElementById('settings-status');
  const showStatus = (element, type, message) => {
    if (!element) return;
    element.hidden = false;
    element.className = `payment-status ${type}`;
    element.textContent = message;
  };

  const showPaymentDemoNotice = (statusElement) => {
    showStatus(
      statusElement,
      'error',
      'Demo only: checkout is not connected, and no payment was made.'
    );
  };

  if (shareButton && shareStatus) {
    shareButton.addEventListener('click', async () => {
      const shareData = {
        title: 'Mopolee Cinema & Exchange',
        text: 'Discover Mopolee Cinema & Exchange. Sign in to explore free films and your personal profile.',
        url: window.location.origin
      };

      try {
        if (navigator.share) {
          await navigator.share(shareData);
          shareStatus.textContent = 'Mopolee demo link shared.';
        } else if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(shareData.url);
          shareStatus.textContent = 'Demo link copied. Share it with friends.';
        } else {
          shareStatus.textContent = `Copy this demo link to share: ${shareData.url}`;
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          shareStatus.textContent = `Could not share automatically. Copy this link instead: ${shareData.url}`;
        }
      }
    });
  }

  const dashboardThemes = {
    ocean: { primary: '#5cc7ff', secondary: '#8c7bff', green: '#4ade80', orange: '#fbbf24' },
    violet: { primary: '#a78bfa', secondary: '#ec4899', green: '#4ade80', orange: '#fbbf24' },
    emerald: { primary: '#34d399', secondary: '#14b8a6', green: '#a3e635', orange: '#fbbf24' },
    sunset: { primary: '#fb923c', secondary: '#f43f5e', green: '#4ade80', orange: '#facc15' }
  };

  const applyDashboardTheme = (themeName, persist = false) => {
    const theme = dashboardThemes[themeName];
    if (!theme) return false;
    const root = document.documentElement;
    root.style.setProperty('--primary', theme.primary);
    root.style.setProperty('--primary-2', theme.secondary);
    root.style.setProperty('--green', theme.green);
    root.style.setProperty('--orange', theme.orange);
    document.querySelectorAll('[data-dashboard-theme]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.dashboardTheme === themeName));
    });

    if (persist) {
      try {
        window.localStorage.setItem('mopolee-dashboard-theme', themeName);
        if (settingsStatus) settingsStatus.textContent = 'Your color theme is saved on this device.';
      } catch {
        if (settingsStatus) settingsStatus.textContent = 'Theme applied for this visit, but this browser could not save the preference.';
      }
    }
    return true;
  };

  document.querySelectorAll('[data-dashboard-theme]').forEach((button) => {
    button.addEventListener('click', () => {
      applyDashboardTheme(button.dataset.dashboardTheme, true);
    });
  });

  try {
    const savedTheme = window.localStorage.getItem('mopolee-dashboard-theme');
    if (savedTheme) applyDashboardTheme(savedTheme);
  } catch {
    if (settingsStatus) settingsStatus.textContent = 'Saved appearance settings are not available in this browser.';
  }

  if (narrationButton) {
    const narrationText = [
      'Welcome to Mopolee Cinema and Exchange.',
      'This is a preview of the app dashboard. The figures shown are sample data, not real account balances or business results.',
      'Use the sidebar to explore the overview, cinema, exchange, wallet, rewards, and tickets.',
      'You can explore sample cinema listings and use the exchange calculator.',
      'Booking and payment controls are demonstrations only. No booking is made and no payment is taken.',
      'Thank you for exploring Mopolee.'
    ].join(' ');
    const speechSupported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;

    if (!speechSupported) {
      narrationButton.disabled = true;
      if (narrationVoiceSelect) narrationVoiceSelect.disabled = true;
      narrationStatus.textContent = 'App narration is not supported by this browser.';
    } else {
      let voices = [];
      const updateNarrationVoices = () => {
        if (!narrationVoiceSelect) return;

        const selectedVoiceURI = narrationVoiceSelect.value;
        voices = window.speechSynthesis.getVoices()
          .filter((voice) => voice.lang.toLowerCase().startsWith('en'))
          .sort((first, second) => first.name.localeCompare(second.name));

        narrationVoiceSelect.replaceChildren(new Option('Automatic voice', ''));
        voices.forEach((voice) => {
          narrationVoiceSelect.add(new Option(`${voice.name} (${voice.lang})`, voice.voiceURI));
        });
        narrationVoiceSelect.value = voices.some((voice) => voice.voiceURI === selectedVoiceURI)
          ? selectedVoiceURI
          : '';
      };

      updateNarrationVoices();
      window.speechSynthesis.addEventListener('voiceschanged', updateNarrationVoices);

      narrationButton.addEventListener('click', () => {
        if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
          window.speechSynthesis.cancel();
          narrationButton.textContent = '▶ Play app narration';
          narrationButton.setAttribute('aria-pressed', 'false');
          narrationStatus.textContent = 'App narration stopped.';
          return;
        }

        const narration = new SpeechSynthesisUtterance(narrationText);
        narration.lang = 'en';
        narration.rate = 0.95;
        if (narrationVoiceSelect && narrationVoiceSelect.value) {
          narration.voice = voices.find((voice) => voice.voiceURI === narrationVoiceSelect.value) || null;
        }
        narration.onstart = () => {
          narrationButton.textContent = '■ Stop narration';
          narrationButton.setAttribute('aria-pressed', 'true');
          narrationStatus.textContent = 'App narration is playing.';
        };
        narration.onend = () => {
          narrationButton.textContent = '▶ Play app narration';
          narrationButton.setAttribute('aria-pressed', 'false');
          narrationStatus.textContent = 'App narration finished.';
        };
        narration.onerror = () => {
          narrationButton.textContent = '▶ Play app narration';
          narrationButton.setAttribute('aria-pressed', 'false');
          narrationStatus.textContent = 'App narration could not be played.';
        };
        window.speechSynthesis.speak(narration);
      });
    }
  }

  const cinemaLibrary = document.getElementById('cinema-library-grid');
  const cinemaLibraryStatus = document.getElementById('cinema-library-status');
  const cinemaUploadPanel = document.getElementById('cinema-admin-upload');
  const cinemaUploadForm = document.getElementById('cinema-upload-form');
  const cinemaUploadStatus = document.getElementById('cinema-upload-status');
  const cinemaUploadProgress = document.getElementById('cinema-upload-progress');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  if (cinemaLibrary && cinemaLibraryStatus) {
    const showCinemaStatus = (element, message, isError = false) => {
      element.textContent = message;
      element.classList.toggle('error', isError);
    };

    const cinemaApi = async (url, options = {}) => {
      const response = await fetch(url, {
        credentials: 'same-origin',
        ...options,
        headers: {
          ...(options.headers || {}),
          ...(options.method && options.method !== 'GET' ? { 'X-CSRF-Token': csrfToken } : {})
        }
      });
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error(`The server returned an invalid response (HTTP ${response.status}).`);
      }
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
      return result;
    };

    const loadCinemaFilms = async () => {
      showCinemaStatus(cinemaLibraryStatus, 'Loading films...');
      try {
        const result = await cinemaApi('/api/cinema/films');
        cinemaLibrary.replaceChildren();
        if (cinemaUploadPanel) {
          cinemaUploadPanel.hidden = !result.is_admin;
          const uploadButton = cinemaUploadForm?.querySelector('button[type="submit"]');
          if (uploadButton) uploadButton.disabled = !result.storage_ready;
          if (result.is_admin && !result.storage_ready && cinemaUploadStatus) {
            showCinemaStatus(cinemaUploadStatus, 'Connect the Cloudflare R2 settings to enable permanent uploads.', true);
          }
        }

        if (!result.films.length) {
          showCinemaStatus(cinemaLibraryStatus, 'The film collection is ready for its first movie.');
          return;
        }

        result.films.forEach((film) => {
          const card = document.createElement('article');
          card.className = 'media-card cinema-film-card';
          if (film.poster_url) {
            const poster = document.createElement('img');
            poster.className = 'cinema-film-poster';
            poster.src = film.poster_url;
            poster.alt = `${film.title} poster`;
            poster.loading = 'lazy';
            card.append(poster);
          } else {
            const placeholder = document.createElement('div');
            placeholder.className = 'cinema-film-poster cinema-film-poster-placeholder';
            placeholder.setAttribute('aria-hidden', 'true');
            placeholder.textContent = 'M';
            card.append(placeholder);
          }
          const copy = document.createElement('div');
          copy.className = 'cinema-film-copy';
          const title = document.createElement('h3');
          title.textContent = film.title;
          const description = document.createElement('p');
          description.textContent = film.description || 'A film from the Mopolee collection.';
          const playButton = document.createElement('button');
          playButton.type = 'button';
          playButton.className = 'primary-btn';
          playButton.dataset.playFilm = film.play_url;
          playButton.textContent = 'Watch film';
          copy.append(title, description, playButton);
          card.append(copy);
          cinemaLibrary.append(card);
        });
        showCinemaStatus(cinemaLibraryStatus, `${result.films.length} film${result.films.length === 1 ? '' : 's'} in the collection.`);
      } catch (error) {
        showCinemaStatus(cinemaLibraryStatus, error.message, true);
      }
    };

    const uploadFileToR2 = (url, file, progressStart, progressEnd) => new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open('PUT', url);
      request.setRequestHeader('Content-Type', file.type);
      request.upload.addEventListener('progress', (event) => {
        if (!event.lengthComputable || !cinemaUploadProgress) return;
        const progress = progressStart + (event.loaded / event.total) * (progressEnd - progressStart);
        cinemaUploadProgress.value = Math.round(progress);
      });
      request.addEventListener('load', () => {
        if (request.status >= 200 && request.status < 300) {
          resolve();
        } else {
          reject(new Error(`Cloudflare upload failed (HTTP ${request.status}). Check the R2 bucket CORS settings and try again.`));
        }
      });
      request.addEventListener('error', () => reject(new Error('Could not reach Cloudflare storage. Check the connection and R2 bucket CORS settings.')));
      request.addEventListener('abort', () => reject(new Error('The film upload was cancelled.')));
      request.send(file);
    });

    if (cinemaUploadForm && cinemaUploadStatus && cinemaUploadProgress) {
      cinemaUploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(cinemaUploadForm);
        const video = formData.get('video');
        const poster = formData.get('poster');
        const title = String(formData.get('title') || '').trim();
        const description = String(formData.get('description') || '').trim();
        if (!(video instanceof File) || !video.size || !formData.get('rights_confirmed')) {
          showCinemaStatus(cinemaUploadStatus, 'Choose an MP4 film and confirm that you have rights to share it.', true);
          return;
        }

        const submitButton = cinemaUploadForm.querySelector('button[type="submit"]');
        let pendingFilmId = '';
        submitButton.disabled = true;
        cinemaUploadProgress.hidden = false;
        cinemaUploadProgress.value = 0;
        showCinemaStatus(cinemaUploadStatus, 'Preparing secure upload...');
        try {
          const intent = await cinemaApi('/api/cinema/upload-intents', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title,
              description,
              video_name: video.name,
              video_type: video.type,
              video_size: video.size,
              poster_name: poster instanceof File && poster.size ? poster.name : '',
              poster_type: poster instanceof File && poster.size ? poster.type : '',
              poster_size: poster instanceof File ? poster.size : 0
            })
          });
          pendingFilmId = intent.film_id;
          showCinemaStatus(cinemaUploadStatus, 'Uploading your film securely...');
          const posterPresent = poster instanceof File && poster.size > 0;
          await uploadFileToR2(intent.video_upload_url, video, 0, posterPresent ? 90 : 98);
          if (posterPresent && intent.poster_upload_url) {
            showCinemaStatus(cinemaUploadStatus, 'Film uploaded. Adding the poster...');
            await uploadFileToR2(intent.poster_upload_url, poster, 90, 98);
          }
          cinemaUploadProgress.value = 99;
          await cinemaApi(`/api/cinema/films/${encodeURIComponent(pendingFilmId)}/publish`, { method: 'POST' });
          cinemaUploadProgress.value = 100;
          showCinemaStatus(cinemaUploadStatus, 'Film published to the shared Cinema collection.');
          cinemaUploadForm.reset();
          await loadCinemaFilms();
        } catch (error) {
          if (pendingFilmId) {
            try {
              await cinemaApi(`/api/cinema/films/${encodeURIComponent(pendingFilmId)}/cancel`, { method: 'POST' });
            } catch (cleanupError) {
              showCinemaStatus(cinemaUploadStatus, `${error.message} Cleanup also failed: ${cleanupError.message}`, true);
              submitButton.disabled = false;
              return;
            }
          }
          showCinemaStatus(cinemaUploadStatus, error.message, true);
        } finally {
          submitButton.disabled = false;
          if (cinemaUploadProgress.value === 100) {
            window.setTimeout(() => {
              cinemaUploadProgress.hidden = true;
              cinemaUploadProgress.value = 0;
            }, 1800);
          }
        }
      });
    }

    cinemaLibrary.addEventListener('click', async (event) => {
      const playButton = event.target.closest('[data-play-film]');
      if (!playButton) return;
      playButton.disabled = true;
      try {
        const result = await cinemaApi(playButton.dataset.playFilm);
        let dialog = document.querySelector('.cinema-player-dialog');
        if (!dialog) {
          dialog = document.createElement('dialog');
          dialog.className = 'cinema-player-dialog';
          dialog.setAttribute('aria-labelledby', 'cinema-player-title');
          const closeButton = document.createElement('button');
          closeButton.type = 'button';
          closeButton.className = 'ghost-btn';
          closeButton.textContent = 'Close';
          closeButton.addEventListener('click', () => dialog.close());
          const playerTitle = document.createElement('h2');
          playerTitle.id = 'cinema-player-title';
          const player = document.createElement('video');
          player.controls = true;
          player.playsInline = true;
          player.preload = 'metadata';
          dialog.append(closeButton, playerTitle, player);
          dialog.addEventListener('close', () => {
            player.pause();
            player.removeAttribute('src');
            player.load();
          });
          document.body.append(dialog);
        }
        dialog.querySelector('#cinema-player-title').textContent = playButton.closest('.cinema-film-card').querySelector('h3').textContent;
        dialog.querySelector('video').src = result.video_url;
        dialog.showModal();
      } catch (error) {
        showCinemaStatus(cinemaLibraryStatus, error.message, true);
      } finally {
        playButton.disabled = false;
      }
    });

    loadCinemaFilms();
  }

  navItems.forEach((item) => {
    item.addEventListener('click', () => {
      navItems.forEach((btn) => btn.classList.remove('active'));
      item.classList.add('active');

      const targetPanel = document.querySelector(item.dataset.target || '');
      if (targetPanel && panels.length) {
        panels.forEach((panel) => {
          panel.hidden = panel !== targetPanel;
        });
      }
    });
  });

  segments.forEach((segment) => {
    segment.addEventListener('click', () => {
      segments.forEach((btn) => btn.classList.remove('active'));
      segment.classList.add('active');
    });
  });

  if (panels.length) {
    panels.forEach((panel, index) => {
      if (index !== 0) panel.hidden = true;
    });
  }

  document.querySelectorAll('[data-open-panel]').forEach((button) => {
    button.addEventListener('click', () => {
      const targetPanel = document.querySelector(button.dataset.openPanel || '');
      const targetNav = document.querySelector(`.nav-item[data-target="${button.dataset.openPanel}"]`);
      if (!targetPanel || !targetNav) return;
      navItems.forEach((item) => item.classList.toggle('active', item === targetNav));
      panels.forEach((panel) => {
        panel.hidden = panel !== targetPanel;
      });
    });
  });

  if (cinemaPreview) {
    cinemaPreview.addEventListener('error', () => {
      const cinemaStatus = document.getElementById('cinema-library-status');
      if (!cinemaPreview.currentSrc && cinemaStatus) return;
      if (cinemaStatus) {
        cinemaStatus.textContent = 'The free preview could not load. Refresh the page or contact the app owner.';
        cinemaStatus.classList.add('error');
      }
    });
    cinemaPreview.addEventListener('loadedmetadata', () => {
      const cinemaStatus = document.getElementById('cinema-library-status');
      if (cinemaStatus && cinemaStatus.classList.contains('error')) {
        cinemaStatus.textContent = '';
        cinemaStatus.classList.remove('error');
      }
    });
  }

  if (upgradeButton) {
    upgradeButton.addEventListener('click', () => {
      showPaymentDemoNotice(upgradeStatus);
    });
  }

  if (walletCheckoutButton && walletAmountInput) {
    walletCheckoutButton.addEventListener('click', () => {
      const amount = Number(walletAmountInput.value || 0);
      if (!amount || amount < 1000) {
        showStatus(walletStatus, 'error', 'Please enter a valid amount greater than ₦1,000.');
        return;
      }
      showPaymentDemoNotice(walletStatus);
    });

    document.querySelectorAll('[data-topup]').forEach((row) => {
      row.addEventListener('click', () => {
        const value = Number(row.dataset.topup || 0);
        walletAmountInput.value = value;
        showStatus(walletStatus, 'success', `Top-up preset selected: ₦${value.toLocaleString()}.`);
      });
    });
  }

  if (bookingForm) {
    bookingForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const movie = document.getElementById('movie-select').value;
      const seat = document.getElementById('seat-select').value;
      showStatus(bookingStatus, 'error', `Demo only: seat ${seat} for ${movie} was not reserved.`);
    });
  }

  if (seatButtons.length) {
    seatButtons.forEach((seat) => {
      if (seat.disabled) return;
      seat.addEventListener('click', () => {
        seatButtons.forEach((item) => item.classList.remove('selected'));
        seat.classList.add('selected');
        const seatValue = seat.textContent.trim();
        const seatSelect = document.getElementById('seat-select');
        if (seatSelect) {
          seatSelect.value = seatValue;
        }
        if (bookingStatus) {
          showStatus(bookingStatus, 'success', `Seat ${seatValue} selected. You can now reserve it.`);
        }
      });
    });
  }

  if (convertRateButton && exchangeAmount && exchangeCurrency && fxResult) {
    const updateFxResult = () => {
      const rate = Number(exchangeCurrency.value || 1530);
      const amount = Number(exchangeAmount.value || 0);
      const total = amount * rate;
      fxResult.textContent = `₦${total.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    convertRateButton.addEventListener('click', updateFxResult);
    exchangeAmount.addEventListener('input', updateFxResult);
    exchangeCurrency.addEventListener('change', updateFxResult);
    updateFxResult();
  }
});
