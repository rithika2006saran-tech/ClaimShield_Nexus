import psycopg
conn = psycopg.connect("postgresql://postgres.bpqtqluulxzrpcjswqep:1512%40Saran.@aws-0-ap-south-1.pooler.supabase.com:6543/postgres")
conn.execute("INSERT INTO user_roles (email, role) VALUES ('rithika.2006saran@gmail.com', 'LEAD'), ('sarveshsivasankaran@gmail.com', 'REVIEWER'), ('sabnish776@gmail.com', 'ANALYST') ON CONFLICT (email) DO UPDATE SET role = EXCLUDED.role;")
conn.commit()
conn.close()
