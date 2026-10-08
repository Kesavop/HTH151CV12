/**
 * WinterRoad - Common JavaScript Helpers
 * Shared across public citizen and municipal admin portals.
 */

const WinterRoad = {
  // Format Indian Rupees
  rs(v) {
    if (v == null || isNaN(v)) return "₹0";
    return "₹" + Math.round(Number(v)).toLocaleString("en-IN");
  },

  // Format in Lakh or Crore
  lakh(v) {
    if (v == null || isNaN(v)) return "₹0 L";
    v = Number(v);
    if (v >= 1e7) return "₹" + (v / 1e7).toFixed(2) + " Cr";
    return "₹" + (v / 1e5).toFixed(1) + " L";
  },

  // Escape HTML entities to prevent XSS
  esc(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[c]));
  },

  // Cookie helpers
  getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  },

  deleteCookie(name) {
    document.cookie = `${name}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;`;
  },

  getAdminToken() {
    return this.getCookie("winterroad_token") || sessionStorage.getItem("winterroad_token") || null;
  },

  async logout() {
    const token = this.getAdminToken();
    try {
      if (token) {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
      }
    } catch (e) {
      console.warn("Logout request failed:", e);
    }
    this.deleteCookie("winterroad_token");
    sessionStorage.removeItem("winterroad_token");
    window.location.href = "/admin/login";
  },

  highlightNav() {
    const path = window.location.pathname.replace(/\/$/, "");
    const current = path === "" ? "/" : path;
    const links = document.querySelectorAll(".site-nav nav a");
    links.forEach(a => {
      const href = a.getAttribute("href")?.replace(/\/$/, "");
      const match = (href === "" ? "/" : href);
      if (match === current) {
        a.classList.add("active");
      }
    });
  }
};

document.addEventListener("DOMContentLoaded", () => {
  WinterRoad.highlightNav();
  const logoutBtn = document.getElementById("nav-logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", e => {
      e.preventDefault();
      WinterRoad.logout();
    });
  }
});
