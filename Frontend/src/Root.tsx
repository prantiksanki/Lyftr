import { useEffect, useState } from "react"
import Home from "./Home"
import Chat from "./Chat"

// Tiny hash router: "#/chat" is the chat, anything else is the home page.
const isChat = () => window.location.hash === "#/chat"

export default function Root() {
  const [chat, setChat] = useState(isChat())

  useEffect(() => {
    const onHash = () => setChat(isChat())
    window.addEventListener("hashchange", onHash)
    return () => window.removeEventListener("hashchange", onHash)
  }, [])

  return chat ? <Chat /> : <Home onStart={() => (window.location.hash = "#/chat")} />
}
