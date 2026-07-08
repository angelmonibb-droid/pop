export const store = {
  user: null,
  game: null,
  setUser(user) {
    this.user = user;
    document.dispatchEvent(new CustomEvent("store:user", { detail: user }));
  },
  setGame(game) {
    this.game = game;
    document.dispatchEvent(new CustomEvent("store:game", { detail: game }));
  },
  clear() {
    this.game = null;
    this.user = null;
  },
};

