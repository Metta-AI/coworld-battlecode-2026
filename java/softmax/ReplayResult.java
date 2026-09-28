package softmax;

import battlecode.schema.*;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPInputStream;

/** Read trusted engine results, never player-controlled stdout. */
public final class ReplayResult {
    public static void main(String[] args) throws Exception {
        byte[] bytes;
        try (var input = new GZIPInputStream(Files.newInputStream(Path.of(args[0])))) {
            bytes = input.readAllBytes();
        }
        var game = GameWrapper.getRootAsGameWrapper(ByteBuffer.wrap(bytes));
        MatchFooter match = null;
        GameFooter footer = null;
        int matches = 0;
        for (int i = 0; i < game.eventsLength(); i++) {
            var event = game.events(i);
            if (event.eType() == Event.MatchFooter) {
                match = (MatchFooter) event.e(new MatchFooter());
                matches++;
            } else if (event.eType() == Event.GameFooter) {
                footer = (GameFooter) event.e(new GameFooter());
            }
        }
        if (matches != 1 || match == null || footer == null || footer.winner() != match.winner()) {
            throw new IllegalStateException("Expected one complete match and consistent game footer");
        }
        // Upstream TeamMapping: NEUTRAL=0, A=1, B=2.
        int winner = match.winner();
        if (winner != 1 && winner != 2) {
            throw new IllegalStateException("Unexpected winning team: " + winner);
        }
        String scores = winner == 1 ? "[1.0,0.0]" : "[0.0,1.0]";
        String result = "{\"scores\":" + scores + ",\"winner_slot\":" + (winner - 1)
            + ",\"rounds\":" + match.totalRounds() + ",\"win_type\":" + match.winType() + "}\n";
        Files.writeString(Path.of(args[1]), result);
    }
}
