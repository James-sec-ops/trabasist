from trabasist_server.db import get_connection

c = get_connection()
c.execute("DELETE FROM steps")
c.execute("DELETE FROM cases")
c.execute("DELETE FROM sqlite_sequence WHERE name IN ('cases', 'steps')")
c.commit()
print("cases left:", c.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
print("steps left:", c.execute("SELECT COUNT(*) FROM steps").fetchone()[0])
c.close()
