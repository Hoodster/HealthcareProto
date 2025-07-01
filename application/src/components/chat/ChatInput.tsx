import { Label } from "radix-ui";
import styles from './Chat.module.scss'

function ChatInput() {
    return (
        <div>
            <Label.Root hidden htmlFor="chatInput"></Label.Root>
            <input className={styles.Input}/>
        </div>
    );
}

export default ChatInput