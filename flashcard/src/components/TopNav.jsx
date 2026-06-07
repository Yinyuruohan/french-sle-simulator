const STREAMLIT_URL = 'http://localhost:8501';

export default function TopNav({ active }) {
  const link = (name) => 'sle-nav-link' + (active === name ? ' active' : '');
  return (
    <nav className="sle-topnav">
      <a className="sle-brand" href={`${STREAMLIT_URL}/?goto=home`}>🇨🇦 SLE Prep</a>
      <a className={link('writing')} href={`${STREAMLIT_URL}/?goto=writing`}>Writing</a>
      <a className={link('reading')} href={`${STREAMLIT_URL}/Reading_Comprehension`}>Reading</a>
      <a className={link('flashcards')} href="#/">Flashcards</a>
    </nav>
  );
}
