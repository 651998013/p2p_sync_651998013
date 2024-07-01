import socket  # สร้างและใช้งาน socket เพื่อเชื่อมต่อ, รับ-ส่งข้อมูลระหว่างโหนด.
import threading  # ใช้ในการจัดการกับการทำงานพร้อมกันของงานหลายๆ งาน.
import json  # เซรียลไลส์และดีเซรียลไลส์ข้อมูลในรูปแบบ JSON ที่ได้รับหรือส่ง.
import sys  # ใช้สำหรับการจัดการพารามิเตอร์ของโปรแกรมและไฟล์ในระบบปฏิบัติการ.
import os  # ใช้ในการทำงานกับไฟล์และระบบปฏิบัติการ.
import secrets  # ใช้สำหรับสร้างหมายเลขสุ่มที่ปลอดภัย.

class Node:  # สร้าง class ที่ชื่อว่า Node
    def __init__(self, host, port):  # กำหนดค่าเริ่มต้นสำหรับโหนด เช่น host, port, และการสร้าง wallet address
        self.host = host  # ที่อยู่ IP ของโหนด
        self.port = port  # หมายเลขพอร์ตของโหนด
        self.peers = []  # เก็บรายการ socket ของ peer ที่เชื่อมต่อ
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.transactions = []  # เก็บรายการ transactions
        self.transaction_file = f"transactions_{port}.json"  # ไฟล์สำหรับบันทึก transactions
        self.wallet_address = self.generate_wallet_address()  # สร้าง wallet address สำหรับโหนดนี้

    def generate_wallet_address(self):  # สร้าง wallet address แบบง่ายๆ (ในระบบจริงจะซับซ้อนกว่านี้มาก)
        return '0x' + secrets.token_hex(20)  # ใช้สร้าง wallet address โดยการเชื่อมต่อ '0x' กับค่าที่ได้จาก secrets.token_hex(20)

    def start(self):  # เริ่มต้นการทำงานของโหนด
        self.socket.bind((self.host, self.port))  # ผูก socket กับ host และ port
        self.socket.listen(1)  # รอรับการเชื่อมต่อจาก clients
        print(f"Node listening on {self.host}:{self.port}")  # แสดงข้อความว่าโหนดถูกเริ่มต้นใช้งานแล้ว
        print(f"Your wallet address is: {self.wallet_address}")  # แสดง wallet address ของโหนด

        self.load_transactions()  # โหลด transactions จากไฟล์ (ถ้ามี)

        accept_thread = threading.Thread(target=self.accept_connections)  # สร้าง thread สำหรับรับการเชื่อมต่อใหม่
        accept_thread.start()  # เริ่มต้น thread

    def accept_connections(self):  # รับการเชื่อมต่อจาก clients
        while True:
            client_socket, address = self.socket.accept()  # รอรับการเชื่อมต่อใหม่
            print(f"New connection from {address}")  # แสดงข้อความว่าเชื่อมต่อใหม่จากที่อยู่ใด

            client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))  # สร้าง thread ใหม่สำหรับจัดการการเชื่อมต่อนี้
            client_thread.start()  # เริ่มต้น thread

    def handle_client(self, client_socket):  # จัดการการเชื่อมต่อของ client
        while True:
            try:
                data = client_socket.recv(1024)  # รับข้อมูลจาก client
                if not data:
                    break  # หากไม่มีข้อมูลเข้ามา ให้หยุดการทำงาน
                message = json.loads(data.decode('utf-8'))  # แปลงข้อมูลที่ได้รับเป็น JSON

                self.process_message(message, client_socket)  # ประมวลผลข้อความที่ได้รับ

            except Exception as e:
                print(f"Error handling client: {e}")  # แสดงข้อผิดพลาดถ้ามี
                break

        client_socket.close()  # ปิดการเชื่อมต่อ

    def connect_to_peer(self, peer_host, peer_port):  # เชื่อมต่อไปยัง peer อื่น
        try:
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # สร้าง socket ใหม่
            peer_socket.connect((peer_host, peer_port))  # เชื่อมต่อไปยัง peer อื่น
            self.peers.append(peer_socket)  # เก็บ socket ที่เชื่อมต่อกับ peer ใหม่
            print(f"Connected to peer {peer_host}:{peer_port}")  # แสดงข้อความว่าเชื่อมต่อสำเร็จ

            self.request_sync(peer_socket)  # ขอข้อมูล transactions ทั้งหมดจาก peer ที่เชื่อมต่อ

            peer_thread = threading.Thread(target=self.handle_client, args=(peer_socket,))  # สร้าง thread สำหรับรับข้อมูลจาก peer นี้
            peer_thread.start()  # เริ่มต้น thread

        except Exception as e:
            print(f"Error connecting to peer: {e}")  # แสดงข้อผิดพลาดถ้ามี

    def broadcast(self, message):  # ส่งข้อมูลไปยังทุก peer ที่เชื่อมต่ออยู่
        for peer_socket in self.peers:
            try:
                peer_socket.send(json.dumps(message).encode('utf-8'))  # ส่งข้อมูลในรูปแบบ JSON
            except Exception as e:
                print(f"Error broadcasting to peer: {e}")  # แสดงข้อผิดพลาดถ้ามี
                self.peers.remove(peer_socket)  # ลบ peer ออกจากรายการถ้ามีข้อผิดพลาด

    def process_message(self, message, client_socket):  # ประมวลผลข้อความที่ได้รับ
        if message['type'] == 'transaction':
            print(f"Received transaction: {message['data']}")  # แสดงข้อมูล transaction ที่ได้รับ
            self.add_transaction(message['data'])  # เพิ่ม transaction ใหม่
        elif message['type'] == 'sync_request':
            self.send_all_transactions(client_socket)  # ส่ง transactions ทั้งหมดไปยังโหนดที่ขอซิงโครไนซ์
        elif message['type'] == 'sync_response':
            self.receive_sync_data(message['data'])  # รับและประมวลผลข้อมูล transactions ที่ได้รับจากการซิงโครไนซ์
        else:
            print(f"Received message: {message}")  # แสดงข้อความที่ได้รับ

    def add_transaction(self, transaction):  # เพิ่ม transaction ใหม่และบันทึกลงไฟล์
        if transaction not in self.transactions:
            self.transactions.append(transaction)  # เพิ่ม transaction ลงในรายการ
            self.save_transactions()  # บันทึก transactions ลงไฟล์
            print(f"Transaction added and saved: {transaction}")  # แสดงข้อความว่า transaction ถูกเพิ่มและบันทึก

    def create_transaction(self, recipient, amount):  # สร้าง transaction ใหม่
        transaction = {
            'sender': self.wallet_address,
            'recipient': recipient,
            'amount': amount
        }
        self.add_transaction(transaction)  # เพิ่ม transaction ใหม่
        self.broadcast({'type': 'transaction', 'data': transaction})  # ส่งข้อมูล transaction ใหม่ไปยังทุก peer

    def save_transactions(self):  # บันทึก transactions ลงไฟล์
        with open(self.transaction_file, 'w') as f:
            json.dump(self.transactions, f)  # บันทึก transactions ในรูปแบบ JSON

    def load_transactions(self):  # โหลด transactions จากไฟล์ (ถ้ามี)
        if os.path.exists(self.transaction_file):
            with open(self.transaction_file, 'r') as f:
                self.transactions = json.load(f)  # โหลด transactions จากไฟล์
            print(f"Loaded {len(self.transactions)} transactions from file.")  # แสดงจำนวน transactions ที่โหลดจากไฟล์

    def request_sync(self, peer_socket):  # ส่งคำขอซิงโครไนซ์ไปยัง peer
        sync_request = json.dumps({"type": "sync_request"}).encode('utf-8')
        peer_socket.send(sync_request)  # ส่งคำขอในรูปแบบ JSON

    def send_all_transactions(self, client_socket):  # ส่ง transactions ทั้งหมดไปยังโหนดที่ขอซิงโครไนซ์
        sync_data = json.dumps({
            "type": "sync_response",
            "data": self.transactions
        }).encode('utf-8')
        client_socket.send(sync_data)  # ส่งข้อมูลในรูปแบบ JSON

    def receive_sync_data(self, sync_transactions):  # รับและประมวลผลข้อมูล transactions ที่ได้รับจากการซิงโครไนซ์
        for tx in sync_transactions:
            self.add_transaction(tx)  # เพิ่ม transaction ใหม่
        print(f"Synchronized {len(sync_transactions)} transactions.")  # แสดงจำนวน transactions ที่ซิงโครไนซ์

if __name__ == "__main__":  # ถ้าโปรแกรมถูกเรียกใช้เป็น main script
    if len(sys.argv) != 2:
        print("Usage: python script.py <port>")  # แสดงข้อความว่าใช้งานอย่างไร
        sys.exit(1)  # ออกจากโปรแกรม

    port = int(sys.argv[1])  # รับหมายเลข port จาก command line argument
    node = Node("0.0.0.0", port)  # ใช้ "0.0.0.0" เพื่อรับการเชื่อมต่อจากภายนอก
    node.start()  # เริ่มต้นโหนด

    while True:
        print("\n1. Connect to a peer")
        print("2. Create a transaction")
        print("3. View all transactions")
        print("4. View my wallet address")
        print("5. Exit")
        choice = input("Enter your choice: ")  # รับตัวเลือกจากผู้ใช้

        if choice == '1':
            peer_host = input("Enter peer host to connect: ")
            peer_port = int(input("Enter peer port to connect: "))
            node.connect_to_peer(peer_host, peer_port)  # เชื่อมต่อไปยัง peer อื่น
        elif choice == '2':
            recipient = input("Enter recipient wallet address: ")
            amount = float(input("Enter amount: "))
            node.create_transaction(recipient, amount)  # สร้าง transaction ใหม่
        elif choice == '3':
            print("All transactions:")
            for tx in node.transactions:
                print(tx)  # แสดงรายการ transactions ทั้งหมด
        elif choice == '4':
            print(f"Your wallet address is: {node.wallet_address}")  # แสดง wallet address ของโหนด
        elif choice == '5':
            break  # ออกจากลูป
        else:
            print("Invalid choice. Please try again.")  # แสดงข้อความว่าตัวเลือกไม่ถูกต้อง

    print("Exiting...")  # แสดงข้อความว่าโปรแกรมกำลังออก
