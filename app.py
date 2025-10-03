from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
import pyodbc
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'secret_key'

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'zewanoreply@gmail.com'
app.config['MAIL_PASSWORD'] = 'gglkkkiepnghfien'  # not Gmail password, use App Password
app.config['MAIL_DEFAULT_SENDER'] = ('Zewa Store', 'zewanoreply@gmail.com')

mail = Mail(app)

# --- Database Connection ---
def get_db_connection():
    return pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=DESKTOP-BMMT23S\\SQLEXPRESS;"
        "Database=Zewa;"
        "Trusted_Connection=yes;"
    )




# --- Home Page ---
@app.route('/')
def index():
    return render_template('index.html')


# --- Register ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash("All fields are required!", "danger")
            return redirect('/register')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO Users (email, username, password)
                VALUES (?, ?, ?)
            """, (email, username, password))
            conn.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect('/login')

        except Exception as e:
            conn.rollback()
            error_message = str(e)

            if "UX_Users_username" in error_message:
                flash("This username is already taken. Please choose another.", "danger")
            elif "PRIMARY KEY" in error_message or "email" in error_message:
                flash("This email is already registered. Please use another.", "danger")
            else:
                flash(f"An error occurred: {error_message}", "danger")

            return redirect('/register')

        finally:
            conn.close()

    return render_template('register.html')







# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT username, email FROM Users WHERE email = ? AND password = ?",
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_name'] = user[0]   # username
            session['user_email'] = user[1]  # email
            flash("Login successful!", "success")
            return redirect('/')
        else:
            flash("Invalid credentials.", "danger")
            return redirect('/login')

    return render_template('login.html')


# --- Shop Page ---
@app.route('/shop')
def shop():
    conn = get_db_connection()
    cursor = conn.cursor()

    selected_category = request.args.get('category')
    selected_subcategory = request.args.get('subcategory')

    cursor.execute("SELECT category_id, name FROM Categories")
    categories = cursor.fetchall()

    cursor.execute("SELECT subcategory_id, name, category_id FROM SubCategories")
    subcategories = cursor.fetchall()

    base_query = """
        SELECT 
            p.product_id, 
            p.name, 
            p.price, 
            p.description,
            c.name AS category_name,
            s.name AS subcategory_name
        FROM Products p
        JOIN Categories c ON p.category_id = c.category_id
        JOIN SubCategories s ON p.subcategory_id = s.subcategory_id
    """

    if selected_category and selected_subcategory:
        cursor.execute(base_query + " WHERE p.category_id = ? AND p.subcategory_id = ?",
                       (selected_category, selected_subcategory))
    elif selected_category:
        cursor.execute(base_query + " WHERE p.category_id = ?", (selected_category,))
    else:
        cursor.execute(base_query)

    products = cursor.fetchall()
    conn.close()

    return render_template("shop.html",
                           products=products,
                           categories=categories,
                           subcategories=subcategories,
                           selected_category=int(selected_category) if selected_category else "",
                           selected_subcategory=int(selected_subcategory) if selected_subcategory else "")



# --- Add to Cart ---
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_email' not in session:
        flash("Please login to add to cart", "warning")
        return redirect(url_for('login'))

    product_id = request.form['product_id']
    product_name = request.form['product_name']
    size = request.form.get('size') or ''
    quantity = int(request.form['quantity'])

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM Cart 
            WHERE product_id = ? AND size = ? AND user_email = ?
        """, (product_id, size, session['user_email']))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE Cart SET quantity = quantity + ?
                WHERE product_id = ? AND size = ? AND user_email = ?
            """, (quantity, product_id, size, session['user_email']))
        else:
            cursor.execute("""
                INSERT INTO Cart (product_id, size, quantity, user_email)
                VALUES (?, ?, ?, ?)
            """, (product_id, size, quantity, session['user_email']))

        conn.commit()
        flash("Product added to cart successfully!", "success")

    except Exception as e:
        flash(f"Error adding to cart: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('cart'))


# --- Cart Page ---
@app.route('/cart')
def cart():
    if 'user_email' not in session:
        flash("Please login to view your cart", "danger")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                c.cart_id,
                c.product_id,
                c.size,
                c.quantity,
                p.price, 
                p.name as product_name,
                p.stock,
                CASE WHEN p.stock < c.quantity THEN 1 ELSE 0 END as out_of_stock
            FROM Cart c
            JOIN Products p ON c.product_id = p.product_id
            WHERE c.user_email = ?
        """, (session['user_email'],))
        items = cursor.fetchall()

        total = sum(item.quantity * item.price for item in items) if items else 0

        return render_template("cart.html",
                               items=items,
                               total=total,
                               any_out_of_stock=any(item.out_of_stock for item in items))

    except Exception as e:
        flash(f"Error loading cart: {str(e)}", "danger")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/update_cart", methods=["POST"])
def update_cart():
    if "user_email" not in session:
        flash("Please log in to update your cart.", "warning")
        return redirect(url_for("login"))

    user_email = session["user_email"]
    product_id = request.form.get("product_id")
    quantity = request.form.get("quantity")

    if not quantity or not quantity.isdigit() or int(quantity) < 1:
        flash("Invalid quantity.", "danger")
        return redirect(url_for("cart"))

    quantity = int(quantity)

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Check stock from Products
    cursor.execute("""
        SELECT stock 
        FROM Products 
        WHERE product_id = ?
    """, (product_id,))
    row = cursor.fetchone()

    if not row:
        flash("Product not found.", "danger")
        conn.close()
        return redirect(url_for("cart"))

    stock_quantity = row[0]

    if quantity > stock_quantity:
        flash(f"Only {stock_quantity} items available in stock.", "danger")
        conn.close()
        return redirect(url_for("cart"))

    # ✅ Update the quantity in Cart
    cursor.execute("""
        UPDATE Cart 
        SET quantity = ? 
        WHERE user_email = ? AND product_id = ?
    """, (quantity, user_email, product_id))
    conn.commit()
    conn.close()

    flash("Cart updated successfully.", "success")
    return redirect(url_for("cart"))




# --- Checkout ---
from flask_mail import Message

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_email' not in session:
        flash("Please login to checkout", "danger")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if request.method == 'GET':
            cursor.execute("""
                SELECT 
                    c.product_id, 
                    c.quantity, 
                    p.price, 
                    p.name as product_name,
                    p.stock,
                    CASE WHEN p.stock < c.quantity THEN 1 ELSE 0 END as out_of_stock
                FROM Cart c
                JOIN Products p ON c.product_id = p.product_id
                WHERE c.user_email = ?
            """, (session['user_email'],))
            cart_items = cursor.fetchall()

            total_amount = sum(item.price * item.quantity for item in cart_items)
            out_of_stock_items = [item for item in cart_items if item.out_of_stock]

            return render_template("checkout.html",
                                   cart_items=cart_items,
                                   total_amount=total_amount,
                                   out_of_stock_items=out_of_stock_items)

        # --- POST handling ---
        conn.autocommit = False

        cursor.execute("""
            SELECT 
                c.product_id, 
                c.quantity, 
                p.price,
                p.stock,
                p.name
            FROM Cart c
            JOIN Products p ON c.product_id = p.product_id
            WHERE c.user_email = ?
        """, (session['user_email'],))
        cart_items = cursor.fetchall()

        if not cart_items:
            flash("Your cart is empty", "warning")
            return redirect(url_for('cart'))

        out_of_stock = []
        for item in cart_items:
            available = item.stock if item.stock is not None else 0
            if item.quantity > available:
                out_of_stock.append({
                    'name': item.name,
                    'requested': item.quantity,
                    'available': available
                })

        if out_of_stock:
            return render_template("checkout.html",
                                   cart_items=cart_items,
                                   total_amount=sum(item.price * item.quantity for item in cart_items),
                                   out_of_stock_items=out_of_stock)

        shipping_info = {
            'name': request.form['name'].strip(),
            'address': request.form['address'].strip(),
            'email': request.form['email'].strip()
        }

        total_amount = sum(item.price * item.quantity for item in cart_items)

        cursor.execute("""
           INSERT INTO Orders (user_email, shipping_name, shipping_address, total_amount)
           VALUES (?, ?, ?, ?)
        """, (session['user_email'], shipping_info['name'], shipping_info['address'], total_amount))

        cursor.execute("SELECT SCOPE_IDENTITY()")
        order_id = int(cursor.fetchone()[0])


        for item in cart_items:
            cursor.execute("""
                INSERT INTO Order_Items (order_id, product_id, quantity, price)
                VALUES (?, ?, ?, ?)
            """, (order_id, item.product_id, item.quantity, item.price))

            cursor.execute("""
                UPDATE Products 
                SET stock = stock - ?
                WHERE product_id = ?
            """, (item.quantity, item.product_id))

        cursor.execute("DELETE FROM Cart WHERE user_email = ?", (session['user_email'],))

        conn.commit()

        # ✅ Send order confirmation email
        # ✅ Send order confirmation email
        try:
            msg = Message(
                subject=f"🛍️ Zewa Order Confirmation #{order_id}",
                sender="zewanoreply@gmail.com",  # store email
                recipients=[shipping_info['email']]   # customer's email
            )

    # Plain-text fallback (for clients that don’t support HTML)
            msg.body = f"""
            Hello {shipping_info['name']},

            Thank you for shopping with Zewa! Your order #{order_id} has been placed successfully.

            Order Total: {total_amount} PKR
            Shipping Address: {shipping_info['address']}

            We’ll notify you once your order is shipped.

            – Zewa Team
            """

    # HTML version
            msg.html = f"""
            <div style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color:#b56576;">Thank you for your order, {shipping_info['name']}!</h2>
                <p>Your order <strong>#{order_id}</strong> has been placed successfully.</p>
        
                <h3>📦 Order Summary</h3>
                <table style="width:100%; border-collapse: collapse;">
                    <tr style="background:#f2f2f2;">
                        <th style="padding:8px; border:1px solid #ddd;">Product</th>
                        <th style="padding:8px; border:1px solid #ddd;">Qty</th>
                        <th style="padding:8px; border:1px solid #ddd;">Price</th>
                    </tr>
                    {''.join([
                        f"<tr><td style='padding:8px; border:1px solid #ddd;'>{item.name}</td>"
                        f"<td style='padding:8px; border:1px solid #ddd;'>{item.quantity}</td>"
                        f"<td style='padding:8px; border:1px solid #ddd;'>{item.price} PKR</td></tr>"
                        for item in cart_items
                    ])}
                </table>

                <p><strong>Total: {total_amount} PKR</strong></p>

                <h3>🚚 Shipping To</h3>
                <p>{shipping_info['name']}<br>{shipping_info['address']}</p>

                <hr>
                <p style="font-size:12px; color:#555;">
                    This is an automated email from Zewa Fashion Store.<br>
                    Need help? Contact us at <a href="mailto:zewasupport@gmail.com">zewasupport@gmail.com</a>
                </p>
            </div>
            """

            mail.send(msg)
        except Exception as mail_error:
         print(f"Email sending failed: {mail_error}")


        flash("Order placed successfully!", "success")
        return redirect(url_for('order_confirmation', order_id=order_id))

    except Exception as e:
        conn.rollback()
        flash(f"Checkout failed: {str(e)}", "danger")
        return redirect(url_for('cart'))
    finally:
        conn.close()



# --- Order Confirmation ---
@app.route('/order-confirmation/<int:order_id>')
def order_confirmation(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT order_id, order_date, total_amount, shipping_address, shipping_name
            FROM Orders 
            WHERE order_id = ?
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            flash("Order not found", "danger")
            return redirect(url_for('index'))

        # Normalize order_date to string
        order_date = order.order_date
        if hasattr(order_date, "strftime"):  # datetime object
            order_date = order_date.strftime("%B %d, %Y")

        order_data = {
            "order_id": order.order_id,
            "order_date": order_date,
            "total_amount": order.total_amount,
            "shipping_address": order.shipping_address,
            "shipping_name": order.shipping_name
        }

        cursor.execute("""
            SELECT oi.quantity, oi.price, p.name as product_name
            FROM Order_Items oi
            JOIN Products p ON oi.product_id = p.product_id
            WHERE oi.order_id = ?
        """, (order_id,))
        items = cursor.fetchall()

        delivery_date = (datetime.now() + timedelta(days=3)).strftime('%B %d, %Y')

        return render_template("order_confirmation.html",
                               order=order_data,
                               items=items,
                               delivery_date=delivery_date)

    except Exception as e:
        flash(f"Error loading order: {str(e)}", "danger")
        return redirect(url_for('index'))
    finally:
        conn.close()


@app.route('/cart/reduce/<int:product_id>', methods=['POST'])
def reduce_quantity(product_id):
    if 'user_email' not in session:
        flash("Please login to update your cart", "danger")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get current quantity
        cursor.execute("""
            SELECT quantity 
            FROM Cart 
            WHERE user_email = ? AND product_id = ?
        """, (session['user_email'], product_id))
        row = cursor.fetchone()

        if row and row[0] > 1:  # <-- FIXED (tuple access)
            # Reduce by 1
            cursor.execute("""
                UPDATE Cart 
                SET quantity = quantity - 1
                WHERE user_email = ? AND product_id = ?
            """, (session['user_email'], product_id))
        else:
            # If only 1 left, remove product from cart
            cursor.execute("""
                DELETE FROM Cart 
                WHERE user_email = ? AND product_id = ?
            """, (session['user_email'], product_id))

        conn.commit()
        flash("Cart updated successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error updating cart: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('cart'))


@app.route('/cart/increase/<int:product_id>', methods=['POST'])
def increase_quantity(product_id):
    if 'user_email' not in session:
        flash("Please login to update your cart", "danger")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check stock before increasing
        cursor.execute("""
            SELECT c.quantity, p.stock
            FROM Cart c
            JOIN Products p ON c.product_id = p.product_id
            WHERE c.user_email = ? AND c.product_id = ?
        """, (session['user_email'], product_id))
        row = cursor.fetchone()

        if row:
            current_qty, stock = row
            if current_qty < stock:  
                # Increase only if stock is available
                cursor.execute("""
                    UPDATE Cart
                    SET quantity = quantity + 1
                    WHERE user_email = ? AND product_id = ?
                """, (session['user_email'], product_id))
                flash("Quantity increased!", "success")
            else:
                flash("Cannot add more, stock limit reached.", "warning")

        conn.commit()

    except Exception as e:
        conn.rollback()
        flash(f"Error updating cart: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('cart'))


@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'user_email' not in session:
        flash("Please login to modify your cart", "danger")
        return redirect(url_for('login'))

    product_id = request.form.get('product_id')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM Cart 
            WHERE user_email = ? AND product_id = ?
        """, (session['user_email'], product_id))

        conn.commit()
        flash("Item removed from cart successfully!", "success")

    except Exception as e:
        conn.rollback()
        flash(f"Error removing item: {str(e)}", "danger")
    finally:
        conn.close()

    return redirect(url_for('cart'))







# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)

